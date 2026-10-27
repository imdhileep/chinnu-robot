s = open("controller.py", encoding="utf-8").read()
if '"/gait"' in s:
    print("already"); raise SystemExit
old = '@app.post("/move/{direction}")'
new = '''# ------------------------------------------------------------------ gait tuning (live, no restart)
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

@app.get("/gait")
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

@app.post("/move/{direction}")'''
assert old in s; s = s.replace(old, new, 1)
open("controller.py", "w", encoding="utf-8").write(s); print("patched")
