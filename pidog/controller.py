import os as _os; _os.environ.setdefault("SUDO_USER", "dk")  # pidog/robot_hat read calibration from $SUDO_USER home
import json
#!/usr/bin/env python3
"""Chinnu controller: PiDog lo run ayye chinna API. Server agent idi call chestundi.
Only allow-listed actions. Pidog() object idi matrame own chestundi.
Audio: /listen records from the mic and returns WAV; /say plays a WAV on the USB speaker.
Wake: background offline KWS thread (chinnu_kws_int8.onnx) sets a wake event on "chinnu";
      "stop" is handled locally (safety, works without the server)."""
import os, sys, time, threading, subprocess, wave, array, math
sys.path.append("/home/dk/.local/lib/python3.13/site-packages")
from fastapi import FastAPI, HTTPException, Header, Request, Response
from fastapi.responses import StreamingResponse
from pidog import Pidog

TOKEN = os.environ.get("CHINNU_TOKEN", "")
MIC = os.environ.get("CHINNU_MIC", "plughw:2,0")
VAD_GATE = float(os.environ.get("CHINNU_VAD_GATE", "14"))   # chunk RMS above this = speech (noise ~6)
VAD_TAIL = float(os.environ.get("CHINNU_VAD_TAIL", "0.8"))   # seconds of silence after speech -> stop
VAD_MAX_WAIT = float(os.environ.get("CHINNU_VAD_MAX_WAIT", "3.5"))  # no speech at all for this long -> give up early

# ---- mic DSP: the HAT mic is very quiet (speech peaks ~70/32768). Pre-gain + WebRTC noise suppression
# + auto gain + VAD makes the wake word and speech far clearer (works at a distance, ignores fan/AC noise).
import sys as _sys
import numpy as np
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "pylib"))
MIC_DSP = os.environ.get("CHINNU_MIC_DSP", "1") == "1"
MIC_PREGAIN = float(os.environ.get("CHINNU_MIC_PREGAIN", "16"))
LISTEN_GATE = float(os.environ.get("CHINNU_LISTEN_GATE", "120"))   # processed-RMS speech gate
try:
    from webrtc_noise_gain import AudioProcessor as _AP
except Exception as _e:
    print(f"[dsp] webrtc_noise_gain unavailable: {_e}", flush=True); _AP = None; MIC_DSP = False

class MicDSP:
    """Feed raw S16 mono 16 kHz bytes (multiples of 160 samples); returns (clean bytes, speech fraction)."""
    def __init__(self, ns=3):
        self.p = _AP(31, ns) if _AP else None
    def process(self, raw):
        if not self.p:
            return raw, 1.0
        x = np.frombuffer(raw, dtype=np.int16).astype(np.int32) * MIC_PREGAIN
        x = np.clip(x, -32768, 32767).astype(np.int16)
        out = []; sp = 0; n = 0
        for k in range(0, len(x) - 159, 160):
            r = self.p.Process10ms(x[k:k + 160].tobytes())
            out.append(r.audio); sp += 1 if r.is_speech else 0; n += 1
        return b"".join(out), (sp / n if n else 0.0)
SPEAKER = os.environ.get("CHINNU_SPEAKER", "plughw:3,0")
KWS_DIR = os.environ.get("CHINNU_KWS_DIR", "/home/dk/pidog_ai")
WAKE_THRESHOLD = float(os.environ.get("CHINNU_WAKE_THRESHOLD", "0.7"))
# TEMP: with the quiet HAT mic the int8 model maps a live "Chinnu" to "come"; treat both as wake until retrain
WAKE_LABELS = set(os.environ.get("CHINNU_WAKE_LABELS", "chinnu,come").split(","))
KWS_RMS_GATE = float(os.environ.get("CHINNU_KWS_RMS_GATE", "10"))  # int16 rms below this = silence

app = FastAPI(title="Chinnu Controller")
dog = Pidog()
lock = threading.Lock()
audio_lock = threading.Lock()
last_cmd = {"name": None, "at": None, "ok": None}
wake_event = threading.Event()
hb = {"last": 0.0, "connected": False, "lost_count": 0}
HB_TIMEOUT = float(os.environ.get("CHINNU_HB_TIMEOUT", "20"))
wake_state = {"enabled": True, "last_wake": None, "last_label": None, "last_prob": 0.0, "kws": False}

# ai_pidog.py lo unna values ne
ACTIONS = {
    "sit":        ("sit",          1,  60),
    "stand":      ("stand",        1,  80),
    "lie":        ("lie",          1,  60),
    "wag_tail":   ("wag_tail",     10, 100),
    "tilt_head":  ("tilting_head", 1,  70),
    "shake_head": ("shake_head",   1,  70),
    "stretch":    ("stretch",      1,  60),
    "forward":    ("forward",      3,  95),
    "backward":   ("backward",     3,  95),
    "turn_left":  ("turn_left",    1,  98),
    "turn_right": ("turn_right",   1,  98),
}

def check(token):
    if TOKEN and token != TOKEN:
        raise HTTPException(401, "bad token")

def rgb(mode, color, bps=1.0):
    try:
        dog.rgb_strip.set_mode(mode, color, bps=bps)
    except Exception:
        pass

def wav_rms(path):
    try:
        with wave.open(path, "rb") as w:
            frames = w.readframes(w.getnframes())
        samples = array.array("h", frames)
        if not samples:
            return 0.0
        return math.sqrt(sum(s * s for s in samples) / len(samples))
    except Exception:
        return 0.0

SIT_PITCH = -40   # sitting tilts the body up, so look down to keep the floor/objects in the camera

def do_action(name):
    act, steps, speed = ACTIONS[name]
    dog.do_action(act, step_count=steps, speed=speed)
    dog.wait_all_done()
    if name in ("sit", "stand", "lie"):
        try:
            p = SIT_PITCH if name == "sit" else 0
            head_state.update(yaw=0, roll=0, pitch=p)
            dog.head_move([[0, 0, p]], immediately=True, speed=60); dog.wait_all_done()
        except Exception as e:
            print("[head pitch]", e, flush=True)

# ------------------------------------------------------------------ wake word
def kws_thread():
    try:
        sys.path.insert(0, KWS_DIR)
        import kws_engine
        eng = kws_engine.KWS(model_path=os.path.join(KWS_DIR, "chinnu_kws_int8.onnx"),
                             labels_path=os.path.join(KWS_DIR, "labels.txt"), threshold=WAKE_THRESHOLD)
        wake_state["kws"] = True
        print("[kws] ready")
    except Exception as e:
        print(f"[kws] disabled: {e}")
        return
    rgb("breath", "yellow", 0.6)
    while True:
        if not wake_state["enabled"] or audio_lock.locked():
            time.sleep(0.2); continue
        if not audio_lock.acquire(blocking=False):
            time.sleep(0.2); continue
        try:
            wav = kws_engine.record_clip(MIC, "/tmp/chinnu_kws.wav", 2)
        except Exception as e:
            print(f"[kws] record error {e}"); time.sleep(1); continue
        finally:
            audio_lock.release()
        import numpy as np
        rms16 = float(np.sqrt(np.mean((wav * 32768.0) ** 2))) if len(wav) else 0.0
        wake_state["last_rms"] = round(rms16, 1)
        if rms16 < KWS_RMS_GATE:
            continue  # silence: the quiet voiceHAT mic needs a gate before the model
        peak = float(np.max(np.abs(wav)))
        if peak > 0:
            wav = np.clip(wav * (0.7 / peak), -1.0, 1.0).astype(np.float32)
        try:
            label, prob = eng.predict_windows(wav)
        except Exception as e:
            print(f"[kws] predict error {e}"); continue
        if label in ("silence", "unknown") or prob < WAKE_THRESHOLD:
            continue
        wake_state.update(last_label=label, last_prob=round(prob, 2))
        print(f"[kws] {label} p={prob:.2f}")
        if label in WAKE_LABELS and prob >= 0.9:
            wake_state["last_wake"] = time.strftime("%H:%M:%S")
            rgb("breath", "cyan", 1.5)
            wake_event.set()
        elif label == "stop":
            # local safety: works even if the server is gone
            dog.body_stop(); dog.head_stop(); dog.tail_stop()
            rgb("boom", "red", 1.0); time.sleep(0.5); rgb("breath", "yellow", 0.6)


# ---------- Porcupine wake word ("Chinnu" custom keyword) ----------
PPN_FILE = os.environ.get("CHINNU_PPN", "/home/dk/chinnu-controller/chinnu.ppn")
PV_KEY_FILE = "/home/dk/chinnu-controller/picovoice.key"
PV_SENS = float(os.environ.get("CHINNU_PV_SENS", "0.6"))

def porcupine_thread():
    try:
        import pvporcupine, struct
        key = open(PV_KEY_FILE).read().strip()
        pv = pvporcupine.create(access_key=key, keyword_paths=[PPN_FILE], sensitivities=[PV_SENS])
    except Exception as e:
        print(f"[porcupine] disabled: {e}", flush=True); return None
    print(f"[porcupine] ready (frame {pv.frame_length}, {pv.sample_rate} Hz)", flush=True)
    time.sleep(3)  # let the module finish loading
    wake_state["kws"] = "porcupine"
    FR = pv.frame_length * 2
    while True:
        if not wake_state["enabled"]:
            time.sleep(0.2); continue
        if not audio_lock.acquire(timeout=1):
            continue
        proc = None
        try:
            proc = subprocess.Popen(["arecord", "-q", "-D", MIC, "-f", "S16_LE", "-r", str(pv.sample_rate), "-c", "1", "-t", "raw"],
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            t0 = time.time()
            while time.time() - t0 < 30.0 and not audio_want.is_set():
                buf = proc.stdout.read(FR)
                if len(buf) < FR: break
                pcm = struct.unpack_from("h" * pv.frame_length, buf)
                if pv.process(pcm) >= 0:
                    _trigger_wake("porcupine")
                    break
        except Exception as e:
            print(f"[porcupine] {e}", flush=True); time.sleep(1)
        finally:
            if proc:
                proc.terminate()
                try: proc.wait(timeout=1)
                except Exception: proc.kill()
            audio_lock.release()
        time.sleep(0.05)

audio_want = threading.Event()   # set by /listen and /say to ask the wake thread to yield the mic quickly
_porc_ok = os.path.exists(PPN_FILE) and os.path.exists(PV_KEY_FILE)
if _porc_ok:
    threading.Thread(target=porcupine_thread, daemon=True).start()

# ---------- openWakeWord custom model ("Chinnu") ----------
OWW_FILE = os.environ.get("CHINNU_OWW", "/home/dk/chinnu-controller/chinnu.onnx")
OWW_THRESH = float(os.environ.get("CHINNU_OWW_THRESH", "0.42"))

def oww_thread():
    try:
        import numpy as np
        from openwakeword.model import Model as OWWModel
        try:
            import openwakeword.utils as _u; _u.download_models(["melspectrogram", "embedding_model"])  # feature models (one-time)
        except Exception as e:
            print(f"[oww] feature model download: {e}", flush=True)
        model = OWWModel(wakeword_model_paths=[OWW_FILE])
        name = list(model.models.keys())[0]
    except Exception as e:
        print(f"[oww] disabled: {e}", flush=True); return
    print(f"[oww] ready: {name} thresh={OWW_THRESH}", flush=True)
    time.sleep(3)
    wake_state["kws"] = "openwakeword"
    CH = 1280  # 80 ms @ 16 kHz
    last_hit = 0.0
    while True:
        if not wake_state["enabled"]:
            time.sleep(0.2); continue
        if not audio_lock.acquire(timeout=1):
            continue
        proc = None
        try:
            proc = subprocess.Popen(["arecord", "-q", "-D", MIC, "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw"],
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            model.reset()
            dsp = MicDSP(ns=1) if MIC_DSP else None   # gentle noise removal for the wake word model
            t0 = time.time(); wmax = 0.0
            while time.time() - t0 < 30.0 and not audio_want.is_set():
                buf = proc.stdout.read(CH * 2)
                if len(buf) < CH * 2: break
                if dsp:
                    pcm = np.frombuffer(dsp.process(buf)[0], dtype=np.int16)
                else:
                    pcm = np.frombuffer(buf, dtype=np.int16)
                    peak = int(np.abs(pcm).max()) if pcm.size else 0
                    if peak > 0 and peak < 8000:            # quiet mic: normalise so the model sees normal levels
                        pcm = (pcm.astype(np.float32) * (8000.0 / peak)).astype(np.int16)
                score = float(model.predict(pcm)[name])
                if score > wmax: wmax = score
                if score >= OWW_THRESH and time.time() - last_hit > 2.0:
                    last_hit = time.time()
                    wake_state["last_prob"] = round(score, 2)
                    _trigger_wake("oww")
                    break
            if wmax >= 0.08: print(f"[oww] window max {wmax:.2f}", flush=True)
        except Exception as e:
            print(f"[oww] {e}", flush=True); time.sleep(1)
        finally:
            if proc:
                proc.terminate()
                try: proc.wait(timeout=1)
                except Exception: proc.kill()
            audio_lock.release()
        time.sleep(0.05)

_oww_ok = os.path.exists(OWW_FILE)
if _oww_ok and not _porc_ok:
    threading.Thread(target=oww_thread, daemon=True).start()

if not _porc_ok and not _oww_ok:
    threading.Thread(target=kws_thread, daemon=True).start()

def watchdog_thread():
    """If the server stops sending heartbeats, stop moving and sit down safely."""
    while True:
        time.sleep(2)
        if hb["last"] == 0.0:
            continue  # never connected yet
        age = time.time() - hb["last"]
        if hb["connected"] and age > HB_TIMEOUT:
            hb["connected"] = False; hb["lost_count"] += 1
            print(f"[watchdog] server lost ({age:.0f}s) -> safe stop")
            try:
                dog.body_stop(); dog.head_stop(); dog.tail_stop()
                if lock.acquire(timeout=3):
                    try:
                        dog.do_action("sit", speed=60); dog.wait_all_done()
                    finally:
                        lock.release()
            except Exception as e:
                print(f"[watchdog] stop error {e}")
            rgb("breath", "red", 0.5)
        elif not hb["connected"] and age <= HB_TIMEOUT:
            hb["connected"] = True
            print("[watchdog] server back")
            rgb("breath", "yellow", 0.6)

threading.Thread(target=watchdog_thread, daemon=True).start()

@app.post("/heartbeat")
def heartbeat(x_token: str = Header(default="")):
    check(x_token)
    hb["last"] = time.time()
    if not hb["connected"]:
        hb["connected"] = True; rgb("breath", "yellow", 0.6)
    return {"ok": True, "connected": True}

# ------------------------------------------------------------------ endpoints
@app.get("/health")
def health():
    return {"ok": True, "robot": "chinnu", "actions": list(ACTIONS), "audio": True, "kws": wake_state["kws"]}

_bat_adc = None
def battery_voltage():
    global _bat_adc
    try:
        from robot_hat import ADC
        if _bat_adc is None: _bat_adc = ADC("A4")
        return round(_bat_adc.read_voltage() * 3, 2)
    except Exception as e:
        print(f"[battery] {e}"); return None

@app.get("/battery")
def battery(x_token: str = Header(default="")):
    check(x_token)
    v = battery_voltage()
    pct = None if v is None else max(0, min(100, round((v - 6.6) / (8.4 - 6.6) * 100)))
    return {"voltage": v, "percent": pct}

@app.get("/status")
def status(x_token: str = Header(default="")):
    check(x_token)
    return {"last": last_cmd, "busy": lock.locked(), "audio_busy": audio_lock.locked(), "wake": wake_state, "heartbeat": {"age": round(time.time() - hb["last"], 1) if hb["last"] else None, "connected": hb["connected"], "lost_count": hb["lost_count"]}}

@app.post("/action/{name}")
def action(name: str, x_token: str = Header(default="")):
    check(x_token)
    if name not in ACTIONS:
        raise HTTPException(400, f"unknown action: {name}")
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "busy")
    try:
        t0 = time.time()
        do_action(name)
        last_cmd.update(name=name, at=time.strftime("%H:%M:%S"), ok=True)
        return {"ok": True, "action": name, "seconds": round(time.time()-t0, 2)}
    except Exception as e:
        last_cmd.update(name=name, at=time.strftime("%H:%M:%S"), ok=False)
        raise HTTPException(500, str(e))
    finally:
        lock.release()

# ------------------------------------------------------------------ continuous movement (remote control)
move_state = {"dir": None, "until": 0.0, "active": False, "speed": 0}
MOVE_SPEED = {"forward": 85, "backward": 85, "turn_left": 90, "turn_right": 90}

def move_thread():
    """Keep feeding gait steps while move_state['until'] is in the future, so walking is continuous
    instead of one step per HTTP call. Holds the action lock while moving."""
    held = False
    while True:
        d = move_state["dir"]
        active = bool(d) and time.time() < move_state["until"]
        if active:
            if not held:
                if not lock.acquire(blocking=False):
                    time.sleep(0.1); continue
                held = True; move_state["active"] = True
                rgb("breath", "cyan", 1.5)
            try:
                if len(dog.legs_action_buffer) < 4:          # queue the next step before the buffer runs dry
                    dog.do_action(d, step_count=1, speed=move_state.get("speed") or MOVE_SPEED.get(d, 95))
            except Exception as e:
                print(f"[move] {e}", flush=True); time.sleep(0.2)
            time.sleep(0.02)
        else:
            if held:
                try: dog.wait_all_done()
                except Exception: pass
                lock.release(); held = False; move_state["active"] = False
                move_state["dir"] = None
                rgb("breath", "yellow", 0.6)
            time.sleep(0.05)

threading.Thread(target=move_thread, daemon=True).start()

# ------------------------------------------------------------------ gait tuning (live, no restart)
from pidog.walk import Walk as _Walk
_GAIT_DEFAULT = {"width": _Walk.LEG_STEP_WIDTH, "height": _Walk.LEG_STEP_HEIGHT, "z": _Walk.Z_ORIGIN, "cog": _Walk.CENTER_OF_GRAVIRTY}

def _gait_apply(width=None, height=None, z=None, cog=None):
    if width is not None:  _Walk.LEG_STEP_WIDTH = int(width)
    if height is not None: _Walk.LEG_STEP_HEIGHT = int(height)
    if z is not None:      _Walk.Z_ORIGIN = int(z)
    if cog is not None:    _Walk.CENTER_OF_GRAVIRTY = int(cog)
    return {"width": _Walk.LEG_STEP_WIDTH, "height": _Walk.LEG_STEP_HEIGHT, "z": _Walk.Z_ORIGIN, "cog": _Walk.CENTER_OF_GRAVIRTY}

_gait_apply(width=int(os.environ.get("CHINNU_GAIT_WIDTH", _GAIT_DEFAULT["width"])),
            height=int(os.environ.get("CHINNU_GAIT_HEIGHT", _GAIT_DEFAULT["height"])),
            z=int(os.environ.get("CHINNU_GAIT_Z", _GAIT_DEFAULT["z"])),
            cog=int(os.environ.get("CHINNU_GAIT_COG", _GAIT_DEFAULT["cog"])))

# ---- straight-line trim: >0 shortens RIGHT-side steps (steers right), <0 shortens LEFT-side steps
_GAIT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gait.json")
gait_trim = {"trim": 0.0}

def _trim_apply(trim):
    t = max(-0.4, min(0.4, float(trim)))
    gait_trim["trim"] = t
    # Walk leg index order: 0 LF, 1 RF, 2 LH, 3 RH  (LEFT turn scales shrink 0 and 2)
    _Walk.LEG_STEP_SCALES_MIDDLE[:] = [1 + min(0, t), 1 - max(0, t), 1 + min(0, t), 1 - max(0, t)]
    return t

def _gait_save():
    try:
        json.dump({**_gait_apply(), "trim": gait_trim["trim"], "speed": MOVE_SPEED.get("forward")}, open(_GAIT_FILE, "w"))
    except Exception as e:
        print(f"[gait] save: {e}", flush=True)

def _gait_load():
    try:
        g = json.load(open(_GAIT_FILE))
        _gait_apply(g.get("width"), g.get("height"), g.get("z"), g.get("cog"))
        _trim_apply(g.get("trim", 0))
        if g.get("speed"):
            for k in MOVE_SPEED: MOVE_SPEED[k] = int(g["speed"])
        print(f"[gait] loaded {g}", flush=True)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[gait] load: {e}", flush=True)

@app.get("/gait")
def gait_get(x_token: str = Header(default="")):
    check(x_token)
    return {"current": _gait_apply(), "trim": gait_trim["trim"], "default": _GAIT_DEFAULT, "speed": MOVE_SPEED}

@app.post("/gait")
def gait_set(width: int = None, height: int = None, z: int = None, cog: int = None, speed: int = None, trim: float = None, x_token: str = Header(default="")):
    """Tune the walking gait live (saved to gait.json): step width/height (mm), body height z, centre of gravity,
    servo speed, trim (-0.4..0.4; positive steers right to cancel a left drift)."""
    check(x_token)
    if speed is not None:
        for k in MOVE_SPEED: MOVE_SPEED[k] = max(30, min(100, int(speed)))
    if trim is not None: _trim_apply(trim)
    cur = _gait_apply(width, height, z, cog)
    _gait_save()
    return {"current": cur, "trim": gait_trim["trim"], "speed": MOVE_SPEED}

# ---- servo calibration (leg offsets, saved to ~/.config/pidog/pidog.conf by robot_hat)
LEG_NAMES = ["LF upper", "LF lower", "RF upper", "RF lower", "LH upper", "LH lower", "RH upper", "RH lower"]

@app.get("/calib")
def calib_get(x_token: str = Header(default="")):
    check(x_token)
    return {"legs": {LEG_NAMES[i]: round(v, 2) for i, v in enumerate(dog.legs.offset)},
            "head": [round(v, 2) for v in dog.head.offset], "tail": [round(v, 2) for v in dog.tail.offset]}

@app.post("/calib/leg")
def calib_leg(i: int, delta: float = 0.0, pose: str = "stand", x_token: str = Header(default="")):
    """Nudge one leg servo offset by delta degrees (clamped to +-20), save, then re-pose so the change is visible."""
    check(x_token)
    if not 0 <= i < 8: raise HTTPException(400, "i must be 0..7")
    if not lock.acquire(timeout=3): raise HTTPException(409, "busy")
    try:
        off = list(dog.legs.offset); off[i] = round(off[i] + float(delta), 2)
        dog.legs.set_offset(off)
        if pose in ("90", "60"):
            angles = [0] * 8 if pose == "90" else [30, -30, -30, 30, 30, -30, -30, 30]
            dog.legs_move([angles], immediately=True, speed=40); dog.wait_legs_done()
        elif pose in ACTIONS:
            act, steps, spd = ACTIONS[pose]; dog.do_action(act, step_count=1, speed=60); dog.wait_all_done()
        return {"leg": LEG_NAMES[i], "offset": dog.legs.offset[i], "all": [round(v, 2) for v in dog.legs.offset]}
    finally:
        lock.release()

@app.post("/calib/pose")
def calib_pose(ruler: int = 90, x_token: str = Header(default="")):
    """Put all legs in the SunFounder calibration pose (same as 0_calibration.py):
    ruler=90 -> all leg angles 0 (90-degree acrylic ruler), ruler=60 -> [30,-30,-30,30,30,-30,-30,30]."""
    check(x_token)
    if not lock.acquire(timeout=3): raise HTTPException(409, "busy")
    try:
        angles = [0] * 8 if ruler == 90 else [30, -30, -30, 30, 30, -30, -30, 30]
        dog.legs_move([angles], immediately=True, speed=40); dog.wait_legs_done()
        return {"ok": True, "ruler": ruler, "angles": angles, "offsets": [round(v, 2) for v in dog.legs.offset]}
    finally:
        lock.release()

# ---- gyro-integrated heading change during the last walk (SH3001 at +-2000 dps -> 16.4 LSB per deg/s)
walk_gyro = {"active": False, "t0": 0.0, "secs": 0.0, "deg": [0.0, 0.0, 0.0]}

def gyro_thread():
    last = time.time()
    while True:
        time.sleep(0.02)
        now = time.time(); dt = now - last; last = now
        active = bool(move_state.get("active"))
        if active and not walk_gyro["active"]:
            walk_gyro.update(active=True, t0=now, deg=[0.0, 0.0, 0.0])
        if active:
            try:
                g = list(dog.gyroData)
                for i in range(3): walk_gyro["deg"][i] += g[i] / 16.4 * dt
            except Exception:
                pass
        if not active and walk_gyro["active"]:
            walk_gyro.update(active=False, secs=round(now - walk_gyro["t0"], 2))

threading.Thread(target=gyro_thread, daemon=True).start()

@app.get("/move/last")
def move_last(x_token: str = Header(default="")):
    """Heading change (deg, per gyro axis) integrated over the most recent continuous walk."""
    check(x_token)
    return {"secs": walk_gyro["secs"], "deg": [round(v, 1) for v in walk_gyro["deg"]], "trim": gait_trim["trim"]}

_gait_load()

@app.post("/move/{direction}")
def move(direction: str, ms: int = 700, speed: int = 0, x_token: str = Header(default="")):
    """Start/extend continuous movement. Client re-posts every ~300 ms while the button is held;
    movement stops `ms` after the last call, or immediately on /move/stop."""
    check(x_token)
    if direction == "stop":
        move_state["until"] = 0.0
        try: dog.legs_stop()
        except Exception: pass
        return {"ok": True, "moving": False}
    if direction not in MOVE_SPEED:
        raise HTTPException(400, f"unknown direction: {direction}")
    if move_state["dir"] not in (None, direction):
        move_state["until"] = 0.0; time.sleep(0.15)      # switch direction cleanly
    move_state["dir"] = direction
    if speed: move_state["speed"] = max(30, min(100, int(speed)))
    move_state["until"] = time.time() + max(100, min(3000, ms)) / 1000.0
    return {"ok": True, "moving": True, "dir": direction}

@app.post("/stop")
def stop(x_token: str = Header(default="")):
    check(x_token)
    move_state["until"] = 0.0
    dog.body_stop(); dog.head_stop(); dog.tail_stop()
    return {"ok": True, "stopped": True}

@app.get("/wake")
def wake(timeout: float = 25, x_token: str = Header(default="")):
    """Long-poll: returns when the wake word was heard (or after `timeout` seconds)."""
    check(x_token)
    woke = wake_event.wait(timeout=max(1, min(float(timeout), 55)))
    if woke:
        wake_event.clear()
    return {"woke": woke, "at": wake_state["last_wake"]}

def _trigger_wake(src):
    wake_state["last_wake"] = time.strftime("%H:%M:%S"); wake_state["last_label"] = src
    rgb("breath", "cyan", 1.5); wake_event.set()
    print(f"[wake] via {src}", flush=True)

@app.post("/wake/trigger")
def wake_trigger(x_token: str = Header(default="")):
    """Manual wake (dashboard mic button) - same effect as hearing the wake word."""
    check(x_token)
    _trigger_wake("button")
    return {"ok": True}

def touch_thread():
    """Touching Chinnu's head = wake word."""
    last = 0
    while True:
        try:
            t = dog.dual_touch.read()
            if t != "N" and time.time() - last > 3:
                last = time.time(); _trigger_wake("touch")
                if lock.acquire(blocking=False):
                    try: dog.do_action("wag_tail", step_count=2, speed=100); dog.wait_all_done()
                    finally: lock.release()
        except Exception as e:
            print(f"[touch] {e}", flush=True); time.sleep(5)
        time.sleep(0.1)
threading.Thread(target=touch_thread, daemon=True).start()

@app.post("/wake/enable")
def wake_enable(on: bool = True, x_token: str = Header(default="")):
    check(x_token)
    wake_state["enabled"] = bool(on)
    if not on:
        wake_event.clear()
    return {"ok": True, "enabled": wake_state["enabled"]}

@app.post("/led")
def led(mode: str = "breath", color: str = "yellow", bps: float = 1.0, x_token: str = Header(default="")):
    check(x_token)
    rgb(mode, color, bps)
    return {"ok": True}

@app.post("/listen")
def listen(seconds: float = 5, x_token: str = Header(default="")):
    """Record up to `seconds` of 16 kHz mono audio, but stop early once speech is followed by
    VAD_TAIL seconds of silence (voice-activity detection). Header X-RMS carries the level."""
    check(x_token)
    seconds = max(1, min(float(seconds), 15))
    audio_want.set()
    got = audio_lock.acquire(timeout=5)  # wait for the kws clip to finish
    audio_want.clear()
    try:
        rgb("breath", "cyan", 1.5)
        path = "/tmp/chinnu_listen.wav"
        import array, wave
        CHUNK = 1600  # 100 ms at 16 kHz mono S16
        proc = subprocess.Popen(["arecord", "-q", "-D", MIC, "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw"],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        frames = []; t0 = time.time(); spoke = False; quiet = 0.0; sq = 0.0; n = 0
        dsp = MicDSP() if MIC_DSP else None
        try:
            while time.time() - t0 < seconds:
                buf = proc.stdout.read(CHUNK * 2)
                if not buf: break
                a = array.array("h", buf); c_rms = (sum(x * x for x in a) / max(1, len(a))) ** 0.5
                sq += c_rms * c_rms; n += 1
                if dsp:
                    clean, frac = dsp.process(buf)
                    frames.append(clean)
                    p_rms = float(np.sqrt(np.mean(np.frombuffer(clean, dtype=np.int16).astype(np.float32) ** 2))) if clean else 0.0
                    is_speech = p_rms >= LISTEN_GATE or (frac >= 0.5 and p_rms >= LISTEN_GATE / 2)
                else:
                    frames.append(buf)
                    is_speech = c_rms >= VAD_GATE
                if is_speech:
                    spoke = True; quiet = 0.0
                elif spoke:
                    quiet += 0.1
                    if quiet >= VAD_TAIL: break
                if not spoke and time.time() - t0 >= VAD_MAX_WAIT: break
        finally:
            proc.terminate()
            try: proc.wait(timeout=1)
            except Exception: proc.kill()
        data = b"".join(frames)
        with wave.open(path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(data)
        rms = (sq / max(1, n)) ** 0.5
        print(f"[listen] {len(data)/32000:.1f}s spoke={spoke} rms={rms:.1f}", flush=True)
        return Response(content=open(path, "rb").read(), media_type="audio/wav",
                        headers={"X-RMS": f"{rms:.1f}", "X-Spoke": "1" if spoke else "0"})
    except Exception as e:
        raise HTTPException(500, f"record failed: {e}")
    finally:
        rgb("breath", "yellow", 0.6)
        if got:
            audio_lock.release()

@app.post("/say")
async def say(request: Request, x_token: str = Header(default="")):
    """Play the WAV in the request body on the speaker. Blocks until playback ends (in a worker thread,
    so the rest of the API keeps responding while Chinnu talks)."""
    check(x_token)
    body = await request.body()
    if len(body) < 100:
        raise HTTPException(400, "empty audio")
    import asyncio
    return await asyncio.get_running_loop().run_in_executor(None, _play_wav, body)

def _play_wav(body):
    audio_want.set()
    got = audio_lock.acquire(timeout=8)
    audio_want.clear()
    try:
        rgb("breath", "green", 2.0)
        path = "/tmp/chinnu_say.wav"
        with open(path, "wb") as f:
            f.write(body)
        t0 = time.time()
        subprocess.run(["aplay", "-q", "-D", SPEAKER, path], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        return {"ok": True, "seconds": round(time.time() - t0, 2)}
    finally:
        rgb("breath", "yellow", 0.6)
        if got:
            audio_lock.release()

@app.post("/say/stream")
async def say_stream(request: Request, x_token: str = Header(default=""), rate: int = 24000, pitch: int = 0):
    """Play raw 16-bit mono PCM streamed in the request body while it arrives (low latency).
    pitch: cents to shift (sox, streaming) — 0 = none."""
    check(x_token)
    import asyncio
    loop = asyncio.get_running_loop()
    audio_want.set()
    got = await loop.run_in_executor(None, lambda: audio_lock.acquire(timeout=8))
    audio_want.clear()
    proc = None; sox = None
    try:
        rgb("breath", "green", 2.0)
        t0 = time.time()
        aplay = ["aplay", "-q", "-D", SPEAKER, "--buffer-time=250000", "-t", "raw", "-r", str(rate), "-f", "S16_LE", "-c", "1", "-"]
        if pitch:
            proc = subprocess.Popen(aplay, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sox = subprocess.Popen(["sox", "-q", "-t", "raw", "-r", str(rate), "-e", "signed", "-b", "16", "-c", "1", "-",
                                    "-t", "raw", "-r", str(rate), "-e", "signed", "-b", "16", "-c", "1", "-",
                                    "pitch", str(pitch)],
                                   stdin=subprocess.PIPE, stdout=proc.stdin, stderr=subprocess.DEVNULL)
            sink = sox.stdin
        else:
            proc = subprocess.Popen(aplay, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sink = proc.stdin
        n = 0
        async for chunk in request.stream():
            if chunk:
                n += len(chunk)
                await loop.run_in_executor(None, sink.write, chunk)
        await loop.run_in_executor(None, sink.close)
        if sox:
            await loop.run_in_executor(None, sox.wait)
            try: proc.stdin.close()
            except Exception: pass
        await loop.run_in_executor(None, proc.wait)
        return {"ok": True, "bytes": n, "seconds": round(time.time() - t0, 2)}
    finally:
        for p in (sox, proc):
            if p and p.poll() is None:
                try: p.kill()
                except Exception: pass
        rgb("breath", "yellow", 0.6)
        if got:
            audio_lock.release()

# ------------------------------------------------------------------ camera (MJPEG)
cam = {"obj": None, "lock": threading.Lock(), "last": None, "at": 0.0, "cv2": None}
CAM_FPS = float(os.environ.get("CHINNU_CAM_FPS", "8"))

def _cam_start():
    try:
        from picamera2 import Picamera2
        import cv2
        p = Picamera2()
        p.configure(p.create_video_configuration(main={"size": (640, 360), "format": "RGB888"}))
        p.start()
        try:  # allow longer exposures + a bit brighter by default (night-friendly)
            from libcamera import controls as lc
            p.set_controls({"AeExposureMode": lc.AeExposureModeEnum.Long, "ExposureValue": 0.7, "FrameDurationLimits": (33333, 125000)})
        except Exception as e:
            print(f"[camera] default controls: {e}")
        cam["obj"] = p; cam["cv2"] = cv2
        print("[camera] ready")
    except Exception as e:
        print(f"[camera] disabled: {e}")

NIGHT_ON = float(os.environ.get("CHINNU_NIGHT_ON", "38"))    # mean brightness below -> night mode
NIGHT_OFF = float(os.environ.get("CHINNU_NIGHT_OFF", "200"))  # above (while in night mode) -> back to auto
cam_night = {"on": False, "checked": 0.0, "mean": 0.0}

def _cam_auto_night(p, frame, now):
    """Every 2 s: switch to high-gain manual exposure in the dark, back to auto when bright."""
    if now - cam_night["checked"] < 2.0:
        return
    cam_night["checked"] = now
    try:
        m = float(frame[::8, ::8].mean()); cam_night["mean"] = m
        if not cam_night["on"] and m < NIGHT_ON:
            p.set_controls({"AeEnable": False, "AnalogueGain": 16.0, "ExposureTime": 120000})
            cam_night["on"] = True; print(f"[camera] night mode ON (mean {m:.0f})")
        elif cam_night["on"] and m > NIGHT_OFF:
            p.set_controls({"AeEnable": True})
            cam_night["on"] = False; print(f"[camera] night mode OFF (mean {m:.0f})")
    except Exception as e:
        print(f"[camera] night: {e}")

@app.get("/camera/night")
def camera_night(x_token: str = Header(default="")):
    check(x_token)
    return cam_night

def _cam_frame():
    p = cam.get("obj")
    if p is None:
        return None
    now = time.time()
    if cam["last"] is not None and now - cam["at"] < 1.0 / CAM_FPS:
        return cam["last"]
    with cam["lock"]:
        frame = p.capture_array()
        _cam_auto_night(p, frame, now)
        ok, jpg = cam["cv2"].imencode(".jpg", frame, [int(cam["cv2"].IMWRITE_JPEG_QUALITY), 70])
        if ok:
            cam["last"] = jpg.tobytes(); cam["at"] = now
    return cam["last"]

threading.Thread(target=_cam_start, daemon=True).start()

@app.get("/snap.jpg")
def snap():
    f = _cam_frame()
    if f is None:
        raise HTTPException(503, "camera unavailable")
    return Response(content=f, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

@app.get("/camera")
def camera():
    boundary = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
    def gen():
        while True:
            f = _cam_frame()
            if f is None:
                time.sleep(0.5); continue
            yield boundary + str(len(f)).encode() + b"\r\n\r\n" + f + b"\r\n"
            time.sleep(1.0 / CAM_FPS)
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

# ------------------------------------------------------------------ volume (USB speaker)
SPK_CARD = os.environ.get("CHINNU_SPK_CARD", "3")
SPK_CTL = os.environ.get("CHINNU_SPK_CTL", "PCM")

def _vol_get():
    out = subprocess.run(["amixer", "-c", SPK_CARD, "sget", SPK_CTL], capture_output=True, text=True).stdout
    import re
    m = re.search(r"\[(\d+)%\].*\[(on|off)\]", out)
    return {"percent": int(m.group(1)) if m else None, "muted": (m.group(2) == "off") if m else None}

@app.get("/volume")
def volume_get(x_token: str = Header(default="")):
    check(x_token)
    return {"ok": True, **_vol_get()}

@app.post("/volume")
def volume_set(percent: int = None, step: int = None, mute: str = None, x_token: str = Header(default="")):
    """percent=0-100 sets; step=+10/-10 adjusts; mute=on|off|toggle."""
    check(x_token)
    if mute is not None:
        subprocess.run(["amixer", "-q", "-c", SPK_CARD, "sset", SPK_CTL, {"on": "mute", "off": "unmute"}.get(mute, "toggle")])
    if percent is not None:
        percent = max(0, min(100, int(percent)))
        subprocess.run(["amixer", "-q", "-c", SPK_CARD, "sset", SPK_CTL, f"{percent}%", "unmute"])
    elif step is not None:
        cur = _vol_get().get("percent") or 0
        subprocess.run(["amixer", "-q", "-c", SPK_CARD, "sset", SPK_CTL, f"{max(0, min(100, cur + int(step)))}%", "unmute"])
    return {"ok": True, **_vol_get()}

# ------------------------------------------------------------------ manual control (D-pad + head)
ACTIONS.update({
    "step_forward":  ("forward",    1, 95),
    "step_backward": ("backward",   1, 95),
    "step_left":     ("turn_left",  1, 98),
    "step_right":    ("turn_right", 1, 98),
})
head_lock = threading.Lock()
head_state = {"yaw": 0, "roll": 0, "pitch": 0}

@app.post("/head")
def head(yaw: float = None, roll: float = None, pitch: float = None, speed: int = 80, x_token: str = Header(default="")):
    """Move the head to absolute angles (deg). yaw -90..90, roll -60..60, pitch -40..30. Omitted axes keep their value."""
    check(x_token)
    if move_state.get("active"):
        return {"ok": True, "skipped": "moving", **head_state}
    if yaw is not None:   head_state["yaw"]   = max(-90, min(90, float(yaw)))
    if roll is not None:  head_state["roll"]  = max(-60, min(60, float(roll)))
    if pitch is not None: head_state["pitch"] = max(-40, min(30, float(pitch)))
    if not head_lock.acquire(blocking=False):
        return {"ok": False, "error": "head busy", **head_state}
    try:
        dog.head_move([[head_state["yaw"], head_state["roll"], head_state["pitch"]]], immediately=True, speed=max(10, min(100, int(speed))))
        return {"ok": True, **head_state}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        head_lock.release()

@app.get("/head")
def head_get(x_token: str = Header(default="")):
    check(x_token)
    return head_state
