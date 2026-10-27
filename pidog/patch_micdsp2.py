import shutil, time, re
fn = 'controller.py'
s = open(fn, encoding='utf-8').read()
shutil.copy(fn, fn + '.bak20')

# 2) wake word: replace per-chunk peak normalisation with the DSP
old = '''            model.reset()
            t0 = time.time(); wmax = 0.0
            while time.time() - t0 < 30.0 and not audio_want.is_set():
                buf = proc.stdout.read(CH * 2)
                if len(buf) < CH * 2: break
                pcm = np.frombuffer(buf, dtype=np.int16)
                peak = int(np.abs(pcm).max()) if pcm.size else 0
                if peak > 0 and peak < 8000:            # quiet mic: normalise so the model sees normal levels
                    pcm = (pcm.astype(np.float32) * (8000.0 / peak)).astype(np.int16)
'''
new = '''            model.reset()
            dsp = MicDSP() if MIC_DSP else None
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
'''
assert s.count(old) == 1, 'oww block'
s = s.replace(old, new)

# 3) /listen: clean audio + smarter VAD (WebRTC voice detection + processed level)
old = '''        frames = []; t0 = time.time(); spoke = False; quiet = 0.0; sq = 0.0; n = 0
        try:
            while time.time() - t0 < seconds:
                buf = proc.stdout.read(CHUNK * 2)
                if not buf: break
                frames.append(buf)
                a = array.array("h", buf); c_rms = (sum(x * x for x in a) / max(1, len(a))) ** 0.5
                sq += c_rms * c_rms; n += 1
                if c_rms >= VAD_GATE:
'''
new = '''        frames = []; t0 = time.time(); spoke = False; quiet = 0.0; sq = 0.0; n = 0
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
'''
assert s.count(old) == 1, 'listen block'
s = s.replace(old, new)

# 1) DSP helper (WebRTC noise suppression + auto gain + VAD) after the MIC/VAD settings
anchor = 'VAD_MAX_WAIT = float(os.environ.get("CHINNU_VAD_MAX_WAIT", "3.5"))'
i = s.index(anchor); j = s.index('\n', i)
s = s[:j + 1] + '''
# ---- mic DSP: the HAT mic is very quiet (speech peaks ~70/32768). Pre-gain + WebRTC noise suppression
# + auto gain + VAD makes the wake word and speech far clearer (works at a distance, ignores fan/AC noise).
import sys as _sys
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
    def __init__(self):
        self.p = _AP(31, 3) if _AP else None
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
'''
# make sure numpy is imported at top level before the class (it is used elsewhere as np)
if '\nimport numpy as np' not in s[:s.index('class MicDSP')]:
    s = s.replace('import sys as _sys\n', 'import sys as _sys\nimport numpy as np\n', 1)

# 4) a little more patience at the end of a sentence (people pause mid-command)
s = s.replace('VAD_TAIL = float(os.environ.get("CHINNU_VAD_TAIL", "0.5"))', 'VAD_TAIL = float(os.environ.get("CHINNU_VAD_TAIL", "0.8"))', 1)
open(fn, 'w', encoding='utf-8').write(s); print('patched')
