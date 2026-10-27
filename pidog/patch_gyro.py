s = open("controller.py", encoding="utf-8").read()
if "walk_gyro" in s:
    print("already"); raise SystemExit
old = "_gait_load()\n"
new = '''# ---- gyro-integrated heading change during the last walk (SH3001 at +-2000 dps -> 16.4 LSB per deg/s)
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
'''
assert s.count(old) == 1; s = s.replace(old, new, 1)
open("controller.py", "w", encoding="utf-8").write(s); print("patched")
