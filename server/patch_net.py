import shutil, time, json, os
# 1) netscan: only real LAN devices (skip docker bridges + IPv6 neighbour entries), drop junk already stored
s = open('netscan.py', encoding='utf-8').read()
s = s.replace("            ip, mac = p[0], p[p.index('lladdr') + 1].lower()\n",
              "            ip, mac = p[0], p[p.index('lladdr') + 1].lower()\n            if not ip.startswith('192.168.1.'): continue\n", 1)
open('netscan.py', 'w', encoding='utf-8').write(s)
if os.path.exists('netdevices.json'):
    d = json.load(open('netdevices.json'))
    d['devices'] = {m: v for m, v in d['devices'].items() if str(v.get('ip', '')).startswith('192.168.1.')}
    json.dump(d, open('netdevices.json', 'w'), indent=1)

# 2) endpoints + service running time in srvpage
s = open('srvpage.py', encoding='utf-8').read(); shutil.copy('srvpage.py', 'srvpage.py.bak_net' + time.strftime('%H%M%S'))
if '/api/net/devices' not in s:
    s = s.replace("    svcs = [{'name': k, 'unit': u, 'state': _sh(['systemctl', 'is-active', u])} for k, u in SERVICES.items()]",
"""    def since_unit(u):
        t = _sh(['systemctl', 'show', u, '-p', 'ActiveEnterTimestamp', '--value'])
        return t.split(' ', 1)[1].rsplit(' ', 1)[0] if t and ' ' in t else ''
    svcs = [{'name': k, 'unit': u, 'state': _sh(['systemctl', 'is-active', u]), 'since': since_unit(u)} for k, u in SERVICES.items()]""", 1)
    s = s.replace("        cont.append({'name': k, 'unit': c, 'state': 'active' if st.startswith('Up') else st})",
                  "        cont.append({'name': k, 'unit': c, 'state': 'active' if st.startswith('Up') else st, 'since': st.replace('Up ', 'up ') if st.startswith('Up') else ''})", 1)
    s += '''

@router.get('/api/net/devices')
def net_devices():
    import netscan; return netscan.listing()

@router.post('/api/net/scan')
def net_scan():
    import netscan; netscan.scan(); return netscan.listing()

@router.post('/api/net/label')
async def net_label(req: __import__('fastapi').Request):
    import netscan; d = await req.json(); return {'ok': netscan.set_label(d.get('mac', ''), d.get('label', ''))}
'''
    open('srvpage.py', 'w', encoding='utf-8').write(s); print('srvpage ok')

# 3) start the scanner in the main dashboard process
s = open('dashboard.py', encoding='utf-8').read()
if 'netscan' not in s:
    s += "\nif not os.environ.get('CHINNU_LAN'):\n    import netscan; netscan.start()\n"
    open('dashboard.py', 'w', encoding='utf-8').write(s); print('dashboard ok')

# 4) page: services 'running since' + Wi-Fi devices card
h = open('server.html', encoding='utf-8').read()
if 'id="net"' not in h:
    h = h.replace("<td class=\"muted\">${esc(v.state)}</td>", "<td class=\"muted\">${esc(v.state)}${v.since?'<br><small>since '+esc(v.since)+'</small>':''}</td>", 1)
    h = h.replace('<div class="card"><h2>Suggestions to add</h2>', '''<div class="card"><div class="top"><h2>Devices on your Wi-Fi <span id="netcount" class="pill"></span></h2><button onclick="scanNet()">Scan now</button></div>
 <div class="muted" style="margin-bottom:8px">Scanned every 5 min. Tap a name to label it. "Today" = minutes seen online today. Phones and watches use private (random) addresses, so the maker is hidden.</div>
 <div class="scroll"><table id="net"></table></div></div>

<div class="card"><h2>Suggestions to add</h2>''', 1)
    h = h.replace('function loadAll(){loadStatus();loadUsage();loadDevices();loadSugg()}', '''async function loadNet(d){const r=d||await j('/api/net/devices');$('netcount').textContent=r.online+' online / '+r.total+' seen · last scan '+(r.last_scan||'-');
 $('net').innerHTML='<tr><th></th><th>Name</th><th>IP</th><th>Maker</th><th class="num">Today</th><th>Last seen</th></tr>'+r.devices.map(x=>`<tr class="${x.online?'ok':''}"><td><span class="dot"></span></td><td><a href="#" onclick="lbl('${x.mac}','${esc(x.label||x.host||'').replace(/'/g,'')}');return false">${esc(x.label||x.host||x.mac)}</a>${x.label&&x.host?'<br><small class="muted">'+esc(x.host)+'</small>':''}</td><td class="muted">${esc(x.ip)}</td><td class="muted"><small>${esc(x.vendor||'')}</small></td><td class="num">${Math.floor(x.today_min/60)}h ${x.today_min%60}m</td><td class="muted"><small>${esc(x.last_seen||'')}</small></td></tr>`).join('')}
async function scanNet(){toast('Scanning…');loadNet(await j('/api/net/scan',{method:'POST'}));toast('Scan done')}
async function lbl(mac,cur){const box=document.createElement('div');box.innerHTML=`<div style="position:fixed;inset:0;background:#0009;display:flex;align-items:center;justify-content:center"><div class="card" style="min-width:280px"><h2>Name this device</h2><input id="lblin" value="${cur}" style="width:100%;padding:8px;border-radius:8px;border:1px solid var(--line);background:#1f2840;color:var(--fg)"><div style="margin-top:10px;display:flex;gap:8px;justify-content:flex-end"><button id="lblc">Cancel</button><button id="lbls">Save</button></div></div></div>`;document.body.appendChild(box);
 box.querySelector('#lblc').onclick=()=>box.remove();box.querySelector('#lbls').onclick=async()=>{await j('/api/net/label',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mac,label:box.querySelector('#lblin').value})});box.remove();loadNet()}}
function loadAll(){loadStatus();loadUsage();loadDevices();loadSugg();loadNet()}''', 1)
    open('server.html', 'w', encoding='utf-8').write(h); print('page ok')
