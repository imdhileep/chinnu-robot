b = open('brain.py', encoding='utf-8').read()
if 'govee_plug' not in b:
    old = '''  {"type": "function", "function": {
    "name": "power_strip",'''
    new = '''  {"type": "function", "function": {
    "name": "govee_plug",
    "description": "Control the Govee smart plugs (each has 2 sockets). target: plug name (both sockets), or a friendly socket name from GOVEE PLUGS in the system prompt, or '<plug> 1' / '<plug> 2'. action: on | off | status | list.",
    "parameters": {"type": "object", "properties": {"target": {"type": "string"}, "action": {"type": "string", "enum": ["on", "off", "status", "list"]}}, "required": ["action"]}}},
  {"type": "function", "function": {
    "name": "power_strip",'''
    assert old in b; b = b.replace(old, new, 1)
    old2 = '        if name == "power_strip":\n'
    new2 = '''        if name == "govee_plug":
            import govee_plug
            a = args.get("action")
            if a == "list": return govee_plug.list_plugs()
            if a == "status": return govee_plug.status(args.get("target"))
            return govee_plug.set_plug(args.get("target", ""), a == "on")
        if name == "power_strip":
'''
    assert old2 in b; b = b.replace(old2, new2, 1)
    old3 = 'POWER STRIP: power_strip controls'
    new3 = 'GOVEE PLUGS: govee_plug controls Govee dual smart plugs: " + "; ".join(f"{k} (socket1={v.get(1, v.get(\'1\', \'?\'))}, socket2={v.get(2, v.get(\'2\', \'?\'))})" for k, v in ((yaml.safe_load(open("config.yaml", encoding="utf-8-sig")).get("govee") or {}).get("sockets") or {}).items()) + ". Use the friendly socket names when Chintu names the appliance. POWER STRIP: power_strip controls'
    assert old3 in b; b = b.replace(old3, new3, 1)
    open('brain.py', 'w', encoding='utf-8').write(b); print('brain ok')

c = open('config.yaml', encoding='utf-8-sig').read()
if 'govee:' not in c:
    c += '\ngovee:                 # Govee dual smart plugs (cloud API); friendly names per socket\n  sockets:\n    Fan:\n      1: fan\n      2: fan plug 2\n    Plug:\n      1: plug 1\n      2: plug 2\n    Dual Smart Plug:\n      1: dual plug 1\n      2: dual plug 2\n'
    open('config.yaml', 'w', encoding='utf-8').write(c); print('config ok')

v = open('voice_agent.py', encoding='utf-8').read()
if "'govee_plug'" not in v:
    v = v.replace("QUICK_ACK = {'robot_action': 'Sare anna!',", "QUICK_ACK = {'robot_action': 'Sare anna!', 'govee_plug': 'Sare anna!',", 1)
    open('voice_agent.py', 'w', encoding='utf-8').write(v); print('voice ok')

d = open('dashboard.py', encoding='utf-8').read()
if '/api/govee' not in d:
    old = "@app.get('/api/strip')"
    new = '''@app.get('/api/govee')
def govee_list():
    import govee_plug
    try: return {'plugs': govee_plug.list_plugs(), 'state': govee_plug.status()}
    except Exception as e: return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.post('/api/govee/{target}/{action}')
def govee_set(target: str, action: str):
    import govee_plug
    history.log('govee', f'{target} {action}')
    try: return govee_plug.set_plug(target, action == 'on')
    except Exception as e: return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.get('/api/strip')'''
    assert old in d; d = d.replace(old, new, 1)
    open('dashboard.py', 'w', encoding='utf-8').write(d); print('dashboard ok')
