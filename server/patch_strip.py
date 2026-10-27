b = open('brain.py', encoding='utf-8').read()
if 'power_strip' not in b:
    old = '''  {"type": "function", "function": {
    "name": "home_light",'''
    new = '''  {"type": "function", "function": {
    "name": "power_strip",
    "description": "Control the smart power strip (PM03) outlets. outlet: 1 | 2 | 3 | usb | all, or the friendly name of what is plugged in (see POWER STRIP in the system prompt). action: on | off | status.",
    "parameters": {"type": "object", "properties": {"outlet": {"type": "string"}, "action": {"type": "string", "enum": ["on", "off", "status"]}}, "required": ["outlet", "action"]}}},
  {"type": "function", "function": {
    "name": "home_light",'''
    assert old in b; b = b.replace(old, new, 1)
    old2 = '        if name == "robot_stop": return robot.stop()\n'
    new2 = '''        if name == "robot_stop": return robot.stop()
        if name == "power_strip":
            import tuya_strip
            if args.get("action") == "status": return tuya_strip.status()
            return tuya_strip.set_outlet(args.get("outlet", "all"), args.get("action") == "on")
'''
    assert old2 in b; b = b.replace(old2, new2, 1)
    old3 = 'HOME CAMERAS: home_camera('
    new3 = 'POWER STRIP: power_strip controls the PM03 smart strip outlets (1, 2, 3, usb) - friendly names: " + ", ".join(f"{k}={v}" for k, v in ((yaml.safe_load(open("config.yaml", encoding="utf-8-sig")).get("strip") or {}).get("outlets") or {}).items()) + ". Use it when Chintu asks to turn something plugged into the strip on/off. HOME CAMERAS: home_camera('
    assert old3 in b; b = b.replace(old3, new3, 1)
    open('brain.py', 'w', encoding='utf-8').write(b); print('brain ok')

c = open('config.yaml', encoding='utf-8-sig').read()
if 'strip:' not in c:
    c += '\nstrip:                 # Tuya/GHome PM03 power strip (tinytuya, local)\n  outlets:\n    1: outlet 1\n    2: outlet 2\n    3: outlet 3\n    usb: usb\n'
    open('config.yaml', 'w', encoding='utf-8').write(c); print('config ok')

v = open('voice_agent.py', encoding='utf-8').read()
if "'power_strip'" not in v:
    v = v.replace("QUICK_ACK = {'robot_action': 'Sare anna!',", "QUICK_ACK = {'robot_action': 'Sare anna!', 'power_strip': 'Sare anna!',", 1)
    open('voice_agent.py', 'w', encoding='utf-8').write(v); print('voice ok')

d = open('dashboard.py', encoding='utf-8').read()
if '/api/strip' not in d:
    old = "@app.post('/api/chat')"
    new = '''@app.get('/api/strip')
def strip_status():
    import tuya_strip
    try: return tuya_strip.status()
    except Exception as e: return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.post('/api/strip/{outlet}/{action}')
def strip_set(outlet: str, action: str):
    import tuya_strip
    history.log('strip', f'{outlet} {action}')
    try: return tuya_strip.set_outlet(outlet, action == 'on')
    except Exception as e: return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.post('/api/chat')'''
    assert old in d; d = d.replace(old, new, 1)
    open('dashboard.py', 'w', encoding='utf-8').write(d); print('dashboard ok')
