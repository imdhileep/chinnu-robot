import shutil
P = '/home/dk/chinnu-controller/controller.py'
shutil.copy(P, P + '.bak_sitpitch')
s = open(P).read()
old = """def do_action(name):
    act, steps, speed = ACTIONS[name]
    dog.do_action(act, step_count=steps, speed=speed)
    dog.wait_all_done()
"""
new = """SIT_PITCH = -25   # sitting tilts the body up, so look down to keep the floor/objects in the camera

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
"""
assert old in s
s = s.replace(old, new, 1)
open(P, 'w').write(s)
print('patched')
