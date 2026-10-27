import shutil, time
ts = time.strftime('%H%M%S')
# behaviors.py: simpler _say
b = open('behaviors.py', encoding='utf-8').read()
b = b.replace("""    try: requests.post('http://127.0.0.1:8081/say', json={'text': text}, timeout=3)
    except Exception: pass
""", "")
open('behaviors.py', 'w', encoding='utf-8').write(b)

# dashboard: init + endpoints
fn = 'dashboard.py'; s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_beh' + ts)
if 'behaviors' not in s:
    s += '''

import behaviors as _beh
_beh.init(ROBOT, HDR)

@app.get('/api/behavior')
def api_behavior():
    return _beh.status()

@app.post('/api/guard/{act}')
def api_guard(act: str):
    return _beh.guard(act == 'on')

@app.post('/api/follow/{act}')
def api_follow(act: str):
    return _beh.follow(act == 'on')
'''
    open(fn, 'w', encoding='utf-8').write(s); print('dashboard ok')

# brain: tools + robot_stop also stops follow
fn = 'brain.py'; s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_beh' + ts)
if '"guard_mode"' not in s:
    tools = '''  {"type": "function", "function": {
    "name": "guard_mode",
    "description": "Guard mode: Chinnu sits and watches the room; if a person who is not Chintu appears, a photo is sent to Chintu's phone (Telegram). Turns itself off when Chintu's face is seen. Use for 'guard mode on/off', 'illu chusko', 'kaapala kaayi'.",
    "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["on", "off", "status"]}}, "required": ["action"]}}},
  {"type": "function", "function": {
    "name": "follow_me",
    "description": "Follow mode: Chinnu walks after the nearest person (camera person detection), stops when close. Use for 'follow me', 'na venaka raa', 'naatho raa'; action off for 'aagu', 'follow aapu'.",
    "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["on", "off", "status"]}}, "required": ["action"]}}},
'''
    anchor = '  {"type": "function", "function": {\n    "name": "who_is_here"'
    assert s.count(anchor) == 1
    s = s.replace(anchor, tools + anchor)
    a2 = '        if name == "who_is_here":\n'
    s = s.replace(a2, '''        if name in ("guard_mode", "follow_me"):
            import requests
            kind = "guard" if name == "guard_mode" else "follow"
            act = args.get("action", "on")
            if act == "status": return requests.get("http://127.0.0.1:8080/api/behavior", timeout=5).json()
            return requests.post(f"http://127.0.0.1:8080/api/{kind}/{act}", timeout=10).json()
''' + a2, 1)
    s = s.replace('        if name == "robot_stop": return robot.stop()',
                  '        if name == "robot_stop":\n            try:\n                import requests; requests.post("http://127.0.0.1:8080/api/follow/off", timeout=5)\n            except Exception: pass\n            return robot.stop()', 1)
    open(fn, 'w', encoding='utf-8').write(s); print('brain ok')

# routines: leaving home -> guard on, im home -> guard off (via shell to the dashboard API)
fn = 'commands.py'; c = open(fn, encoding='utf-8').read()
if "kind == 'guard'" not in c:
    a = "        if kind == 'sleep':"
    c = c.replace(a, "        if kind in ('guard', 'follow') and len(parts) >= 2:\n            return requests.post(f'http://127.0.0.1:8080/api/{kind}/{parts[1]}', timeout=10).json()\n" + a, 1)
    open(fn, 'w', encoding='utf-8').write(c); print('commands ok')
y = open('commands.yaml', encoding='utf-8').read()
if 'guard on' not in y:
    y = y.replace("    - strip usb off\n    - robot sit\n", "    - strip usb off\n    - guard on\n", 1)
    y = y.replace("  say: \"Welcome back anna! Miss ayya.\"\n  steps:\n", "  say: \"Welcome back anna! Miss ayya.\"\n  steps:\n    - guard off\n", 1)
    y = y.replace("#   brain <prompt>", "#   guard on|off                        (guard mode: photo to Telegram if a stranger appears)\n#   follow on|off\n#   brain <prompt>", 1)
    open('commands.yaml', 'w', encoding='utf-8').write(y); print('yaml ok')
