import shutil, time
# dashboard: start shaper + API
s = open('dashboard.py', encoding='utf-8').read()
if 'wifishaper' not in s:
    s += "\nif not os.environ.get('CHINNU_LAN'):\n    import wifishaper; wifishaper.start()\n"
    open('dashboard.py', 'w', encoding='utf-8').write(s)
p = open('srvpage.py', encoding='utf-8').read()
if '/api/wifi/clients' not in p:
    p += '''

@router.get('/api/wifi/clients')
def wifi_clients():
    import wifishaper, os
    pw = ''
    try: pw = open(os.path.join(BASE, 'chinnu_wifi_pass')).read().strip()
    except Exception: pass
    return {'ssid': 'Chinnu-WiFi', 'password': pw, 'devices': wifishaper.listing()}

@router.post('/api/wifi/limit')
async def wifi_limit(req: __import__('fastapi').Request):
    import wifishaper; d = await req.json()
    return {'ok': True, 'limit': wifishaper.set_limit(d['mac'], d.get('down'), d.get('up'), d.get('label'))}
'''
    open('srvpage.py', 'w', encoding='utf-8').write(p)
# brain tool: "Chinnu, tablet speed 5 Mbps"
b = open('brain.py', encoding='utf-8').read()
if '"wifi_speed"' not in b:
    shutil.copy('brain.py', 'brain.py.bak_wifi' + time.strftime('%H%M%S'))
    tool = '''  {"type": "function", "function": {
    "name": "wifi_speed",
    "description": "Set or remove the internet speed limit of a device on Chinnu-WiFi (the server hotspot). device = its name/label as Chintu says it; mbps = limit (0 = unlimited). Use 'list' as device to see connected devices.",
    "parameters": {"type": "object", "properties": {"device": {"type": "string"}, "mbps": {"type": "number"}}, "required": ["device"]}}},
'''
    anchor = '  {"type": "function", "function": {\n    "name": "who_is_here"'
    assert b.count(anchor) == 1
    b = b.replace(anchor, tool + anchor)
    a2 = '        if name == "who_is_here":\n'
    b = b.replace(a2, '''        if name == "wifi_speed":
            import wifishaper
            dev = args.get("device", "")
            if dev.lower() in ("list", "all", ""): return {"devices": wifishaper.listing()}
            r = wifishaper.find(dev)
            if not r: return {"ok": False, "error": f"no device named '{dev}' on Chinnu-WiFi", "devices": [x['label'] or x['mac'] for x in wifishaper.listing()]}
            mb = args.get("mbps")
            if mb is None: return {"ok": True, "device": r}
            return {"ok": True, "device": r["label"] or r["mac"], "limit": wifishaper.set_limit(r["mac"], down=mb, up=(mb / 2 if mb else 0))}
''' + a2, 1)
    open('brain.py', 'w', encoding='utf-8').write(b)
# page card
h = open('server.html', encoding='utf-8').read()
if 'id="wifi"' not in h:
    h = h.replace('<div class="card"><div class="top"><h2>Devices on your Wi-Fi', '''<div class="card"><div class="top"><h2>Chinnu-WiFi · speed limits</h2><span class="muted" id="wifipw"></span></div>
 <div class="muted" style="margin-bottom:8px">Devices joined to <b>Chinnu-WiFi</b> can be limited. 0 = unlimited. Upload is limited to half of download.</div>
 <table id="wifi"></table></div>

<div class="card"><div class="top"><h2>Devices on your Wi-Fi''', 1)
    h = h.replace('function loadAll(){', '''async function loadWifi(){const r=await j('/api/wifi/clients');$('wifipw').innerHTML='password: <b>'+esc(r.password)+'</b>';
 $('wifi').innerHTML='<tr><th></th><th>Device</th><th>IP</th><th>Limit (Mbps)</th><th></th></tr>'+(r.devices.length?r.devices.map(x=>`<tr class="${x.online?'ok':''}"><td><span class="dot"></span></td><td>${esc(x.label||x.mac)}</td><td class="muted">${esc(x.ip||'offline')}</td><td><input type="number" min="0" step="1" value="${x.down||0}" id="lim_${x.mac.replace(/:/g,'')}" style="width:80px;padding:5px;border-radius:8px;border:1px solid var(--line);background:#1f2840;color:var(--fg)"></td><td><button onclick="setLim('${x.mac}')">Set</button></td></tr>`).join(''):'<tr><td class="muted">No devices on Chinnu-WiFi yet. Join it from a phone/tablet with the password above.</td></tr>')}
async function setLim(mac){const v=parseFloat($('lim_'+mac.replace(/:/g,'')).value)||0;await j('/api/wifi/limit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mac,down:v,up:v/2})});toast(v?('Limited to '+v+' Mbps'):'Unlimited');loadWifi()}
function loadAll(){loadWifi();''', 1)
    open('server.html', 'w', encoding='utf-8').write(h)
o = open('owner.py', encoding='utf-8').read()   # wifi_speed is owner-only (not in GUEST_TOOLS) - nothing to do
print('ok')
