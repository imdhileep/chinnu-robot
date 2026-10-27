s = open("controller.py", encoding="utf-8").read()
if "/move/stop" in s:
    print("already"); raise SystemExit
old = '@app.post("/stop")\ndef stop('
new = '''# ------------------------------------------------------------------ continuous movement (remote control)
move_state = {"dir": None, "until": 0.0, "active": False}
MOVE_SPEED = {"forward": 98, "backward": 95, "turn_left": 98, "turn_right": 98}

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
                    dog.do_action(d, step_count=1, speed=MOVE_SPEED.get(d, 95))
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

@app.post("/move/{direction}")
def move(direction: str, ms: int = 700, x_token: str = Header(default="")):
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
    move_state["until"] = time.time() + max(100, min(3000, ms)) / 1000.0
    return {"ok": True, "moving": True, "dir": direction}

@app.post("/stop")
def stop('''
assert old in s; s = s.replace(old, new, 1)
open("controller.py", "w", encoding="utf-8").write(s); print("patched")
