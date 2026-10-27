s = open("controller.py", encoding="utf-8").read()
if "_GAIT_FILE" in s:
    print("already"); raise SystemExit
old = '''@app.get("/gait")
def gait_get(x_token: str = Header(default="")):
    check(x_token)
    return {"current": _gait_apply(), "default": _GAIT_DEFAULT, "speed": MOVE_SPEED}

@app.post("/gait")
def gait_set(width: int = None, height: int = None, z: int = None, cog: int = None, speed: int = None, x_token: str = Header(default="")):
    """Tune the walking gait live: step width/height (mm), body height z, centre of gravity, servo speed."""
    check(x_token)
    if speed is not None:
        for k in MOVE_SPEED: MOVE_SPEED[k] = max(30, min(100, int(speed)))
    return {"current": _gait_apply(width, height, z, cog), "speed": MOVE_SPEED}
'''
new = '''# ---- straight-line trim: >0 shortens RIGHT-side steps (steers right), <0 shortens LEFT-side steps
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
        if pose in ACTIONS:
            act, steps, spd = ACTIONS[pose]; dog.do_action(act, step_count=1, speed=60); dog.wait_all_done()
        return {"leg": LEG_NAMES[i], "offset": dog.legs.offset[i], "all": [round(v, 2) for v in dog.legs.offset]}
    finally:
        lock.release()

_gait_load()
'''
assert old in s; s = s.replace(old, new, 1)
if "\nimport json" not in s and "import json" not in s.split("\n\n")[0]:
    s = "import json\n" + s
open("controller.py", "w", encoding="utf-8").write(s); print("patched")
