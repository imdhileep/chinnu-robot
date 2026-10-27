s = open("controller.py", encoding="utf-8").read()
if '"/calib/pose"' in s:
    print("already"); raise SystemExit
old = "_gait_load()\n"
new = '''@app.post("/calib/pose")
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

_gait_load()
'''
assert s.count(old) == 1; s = s.replace(old, new, 1)
# calib_leg: allow re-posing into the calibration pose after a nudge
s = s.replace('''        if pose in ACTIONS:
            act, steps, spd = ACTIONS[pose]; dog.do_action(act, step_count=1, speed=60); dog.wait_all_done()''',
'''        if pose in ("90", "60"):
            angles = [0] * 8 if pose == "90" else [30, -30, -30, 30, 30, -30, -30, 30]
            dog.legs_move([angles], immediately=True, speed=40); dog.wait_legs_done()
        elif pose in ACTIONS:
            act, steps, spd = ACTIONS[pose]; dog.do_action(act, step_count=1, speed=60); dog.wait_all_done()''', 1)
open("controller.py", "w", encoding="utf-8").write(s); print("patched")
