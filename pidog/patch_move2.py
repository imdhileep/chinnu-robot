s = open("controller.py", encoding="utf-8").read()
if '"speed": 0' in s:
    print("already"); raise SystemExit
rep = [
 ('def move(direction: str, ms: int = 700, x_token: str = Header(default="")):',
  'def move(direction: str, ms: int = 700, speed: int = 0, x_token: str = Header(default="")):'),
 ('    move_state["dir"] = direction\n    move_state["until"] = time.time() + max(100, min(3000, ms)) / 1000.0',
  '    move_state["dir"] = direction\n    if speed: move_state["speed"] = max(30, min(100, int(speed)))\n    move_state["until"] = time.time() + max(100, min(3000, ms)) / 1000.0'),
 ('move_state = {"dir": None, "until": 0.0, "active": False}',
  'move_state = {"dir": None, "until": 0.0, "active": False, "speed": 0}'),
 ('                    dog.do_action(d, step_count=1, speed=MOVE_SPEED.get(d, 95))',
  '                    dog.do_action(d, step_count=1, speed=move_state.get("speed") or MOVE_SPEED.get(d, 95))'),
 ('MOVE_SPEED = {"forward": 98, "backward": 95, "turn_left": 98, "turn_right": 98}',
  'MOVE_SPEED = {"forward": 85, "backward": 85, "turn_left": 90, "turn_right": 90}'),
 ('    check(x_token)\n    if yaw is not None:   head_state["yaw"]',
  '    check(x_token)\n    if move_state.get("active"):\n        return {"ok": True, "skipped": "moving", **head_state}\n    if yaw is not None:   head_state["yaw"]'),
]
for a, b in rep:
    assert a in s, a[:50]
    s = s.replace(a, b, 1)
open("controller.py", "w", encoding="utf-8").write(s); print("patched")
