import re
"""Chinnu phone app: a mobile-first PWA page (/m) + server status/control APIs.
Included by dashboard.py via app.include_router(mobile.router). Reuses the dashboard's /api/* endpoints."""
import os, subprocess, time, shutil
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

router = APIRouter()
SERVICES = ['chinnu-dashboard', 'chinnu-voice', 'cync2mqtt', 'chinnu-alexa', 'chinnu-display-keepalive']

def _sh(cmd, timeout=8):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except Exception as e:
        return f'err: {e}'

@router.get('/api/server')
def server_status():
    temp = _sh("vcgencmd measure_temp | cut -d= -f2")
    up = _sh("uptime -p | sed 's/^up //'")
    load = _sh("cut -d' ' -f1-3 /proc/loadavg")
    mem = _sh("free -m | awk 'NR==2{printf \"%d/%d MB\", $3, $2}'")
    disk = _sh("df -h / | awk 'NR==2{print $3\" / \"$2\" (\"$5\")\"}'")
    ts = _sh("tailscale ip -4 2>/dev/null | head -1")
    svcs = {s: _sh(f'systemctl is-active {s}') for s in SERVICES}
    return {'temp': temp, 'uptime': up, 'load': load, 'mem': mem, 'disk': disk, 'tailscale': ts, 'services': svcs,
            'time': time.strftime('%H:%M:%S')}

@router.post('/api/service/{name}/{act}')
def service_ctl(name: str, act: str):
    if name not in SERVICES or act not in ('restart', 'stop', 'start'):
        return JSONResponse({'ok': False, 'error': 'not allowed'}, status_code=400)
    out = _sh(f'sudo systemctl {act} {name} 2>&1', timeout=30)
    return {'ok': True, 'out': out}

@router.post('/api/robot/{act}')
def robot_ctl(act: str):
    """restart = restart PiDog controller service; reboot = reboot the PiDog Pi."""
    import requests
    if act == 'restart':
        out = _sh('ssh -o BatchMode=yes -o ConnectTimeout=5 dk@192.168.1.208 "sudo systemctl restart chinnu-controller" 2>&1', 40)
        return {'ok': True, 'out': out}
    return JSONResponse({'ok': False, 'error': 'not allowed'}, status_code=400)

@router.get('/manifest.json')
def manifest():
    return JSONResponse({
        'name': 'Chinnu', 'short_name': 'Chinnu', 'start_url': '/m', 'display': 'standalone',
        'background_color': '#0b0f1a', 'theme_color': '#0b0f1a',
        'icons': [{'src': '/icon.svg', 'sizes': 'any', 'type': 'image/svg+xml'},
                  {'src': '/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
                  {'src': '/icon-512.png', 'sizes': '512x512', 'type': 'image/png'}]})

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" rx="110" fill="#10162a"/>
<circle cx="176" cy="230" r="62" fill="#4cc9f0"/><circle cx="336" cy="230" r="62" fill="#4cc9f0"/>
<circle cx="190" cy="244" r="20" fill="#0b0f1a"/><circle cx="350" cy="244" r="20" fill="#0b0f1a"/>
<path d="M196 350 q60 60 120 0" stroke="#4cc9f0" stroke-width="22" fill="none" stroke-linecap="round"/></svg>"""

@router.get('/icon.svg')
def icon_svg():
    return Response(ICON_SVG, media_type='image/svg+xml')

def _png_icon(size):
    p = f'/tmp/chinnu_icon_{size}.png'
    if not os.path.exists(p):
        svg = f'/tmp/chinnu_icon.svg'
        open(svg, 'w').write(ICON_SVG)
        if shutil.which('rsvg-convert'):
            subprocess.run(['rsvg-convert', '-w', str(size), '-h', str(size), svg, '-o', p])
        elif shutil.which('convert'):
            subprocess.run(['convert', '-background', 'none', '-resize', f'{size}x{size}', svg, p])
    return p if os.path.exists(p) else None

@router.get('/icon-{size}.png')
def icon_png(size: int):
    p = _png_icon(size if size in (180, 192, 512) else 192)
    if p:
        return Response(open(p, 'rb').read(), media_type='image/png')
    return Response(ICON_SVG, media_type='image/svg+xml')

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Chinnu</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no">
<link rel="manifest" href="/manifest.json"><link rel="apple-touch-icon" href="/icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Chinnu"><meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"><meta name="theme-color" content="#0b0f1a">
<style>
:root{--bg:#0b0f1a;--card:#10162a;--fg:#e8ecf4;--muted:#8a93a8;--accent:#4cc9f0;--ok:#3ddc84;--warn:#ffb020;--bad:#ff5a5f}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{height:100%;background:var(--bg);color:var(--fg);font-family:-apple-system,system-ui,Roboto,sans-serif;overscroll-behavior:none}
body{display:flex;flex-direction:column;padding-top:env(safe-area-inset-top)}
#top{display:flex;align-items:center;gap:10px;padding:10px 14px}
#top h1{font-size:18px;flex:1}.dot{width:10px;height:10px;border-radius:50%;background:var(--bad);display:inline-block}.dot.ok{background:var(--ok)}
#st{font-size:13px;color:var(--muted)}
main{flex:1;overflow:auto;padding:0 12px 90px}.tab{display:none}.tab.on{display:block}
.card{background:var(--card);border-radius:16px;padding:12px;margin-bottom:12px}
h3{font-size:12px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase;margin-bottom:8px}
.row{display:flex;gap:8px;margin-bottom:8px}.row:last-child{margin-bottom:0}
button{flex:1;font-size:16px;padding:14px 6px;border:0;border-radius:12px;background:#1f2a48;color:var(--fg);font-weight:600}
button:active{background:var(--accent);color:#000}button.stop{background:#6b1f24}button.light{background:#3a3516}button.vol{background:#1d3a2a}button.rec{background:#5a2030}button.talk{background:#1d3a5a}
.face{display:flex;align-items:center;gap:14px}.eyes{display:flex;gap:16px}.eye{width:36px;height:36px;border-radius:50%;background:var(--accent);position:relative;transition:all .25s}
.eye:after{content:"";position:absolute;width:12px;height:12px;border-radius:50%;background:var(--bg);top:12px;left:12px}
.listening .eye{background:var(--ok)}.thinking .eye{background:var(--warn);height:20px;border-radius:40%}.thinking .eye:after{top:4px}.speaking .eye{animation:bob .4s infinite alternate}.error .eye{background:var(--bad)}
@keyframes bob{from{transform:translateY(0)}to{transform:translateY(-6px)}}
#mode{font-size:14px;color:var(--muted)}#bat{font-size:13px;color:var(--muted)}
#chat{display:flex;flex-direction:column;gap:8px;max-height:45vh;overflow:auto;font-size:16px;line-height:1.35}
.msg{padding:8px 12px;border-radius:12px;max-width:92%}.chintu{background:#1b2440;align-self:flex-end}.chinnu{background:#163a3a;align-self:flex-start}.msg small{display:block;color:var(--muted);font-size:11px}
#inrow{display:flex;gap:8px;margin-top:10px}#inrow input{flex:1;font-size:16px;padding:12px;border-radius:12px;border:0;background:#1b2440;color:var(--fg)}#inrow button{flex:0 0 auto;padding:12px 16px}
.dpad{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}.dpad button{font-size:26px;padding:18px 0}.dpad button.on{background:var(--accent);color:#000}
label{font-size:13px;color:var(--muted);display:flex;justify-content:space-between;margin-top:6px}input[type=range]{width:100%;height:40px;accent-color:var(--accent)}
#cam{background:#000;border-radius:12px;overflow:hidden;aspect-ratio:16/9;position:relative;margin-bottom:10px}#cam img{width:100%;height:100%;object-fit:contain;display:none}
#cam button{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);flex:none;padding:10px 18px}#cam.on button{top:auto;bottom:8px;left:auto;right:8px;transform:none;font-size:13px;padding:6px 10px;opacity:.8}
.kv{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:14px}.kv span:nth-child(odd){color:var(--muted)}
.svc{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #1b2440;font-size:14px}.svc:last-child{border:0}.svc .n{flex:1}.svc button{flex:0 0 auto;padding:8px 12px;font-size:13px}
nav{position:fixed;left:0;right:0;bottom:0;display:flex;background:#0e1424;border-top:1px solid #1b2440;padding-bottom:env(safe-area-inset-bottom)}
nav button{background:none;border-radius:0;padding:10px 0 8px;font-size:12px;color:var(--muted);font-weight:500}nav button.on{color:var(--accent)}nav button span{display:block;font-size:22px;margin-bottom:2px}
</style></head><body>
<div id="top"><h1>Chinnu</h1><span class="dot" id="dot"></span><span id="st">...</span></div>
<div id="netban" style="display:none;margin:8px 12px 0;padding:10px 12px;border-radius:12px;background:#7a1d1d;color:#fff;font-size:14px;font-weight:600"></div>
<main>
<section class="tab on" id="t-home">
 <div class="card"><div class="face idle" id="face"><div class="eyes"><div class="eye"></div><div class="eye"></div></div><div><div id="mode">idle</div><div id="bat"></div></div></div></div>
 <div class="card"><h3>Who is talking? <span id="own" style="float:right;font-size:13px">...</span></h3><div style="display:flex;gap:8px"><button style="flex:1;padding:12px" onclick="ownSet('unlock')">&#128275; Its me (guest off)</button><button style="flex:1;padding:12px" onclick="ownSet('lock')">&#128274; Guest mode ON</button></div><div style="font-size:12px;color:var(--muted);margin-top:6px">Chinnu always treats you as owner. Guest mode turns on only when you tap it here, and stays on until you tap Its me.</div></div>
 <div class="card"><button id="ptt" class="talk" style="width:100%;padding:22px;font-size:18px">&#127897; Hold to talk (phone mic)</button><div id="pttmsg" style="font-size:13px;color:var(--muted);margin-top:6px;text-align:center">Hold, speak, release &mdash; Chinnu answers out loud</div><button id="glb" onclick="glToggle()" style="width:100%;margin-top:8px;font-size:14px"></button></div>
 <div class="card"><div class="row"><button class="talk" onclick="post('/api/wake')">&#127908; Talk</button><button onclick="act('sit')">Sit</button><button onclick="act('stand')">Stand</button><button onclick="act('lie')">Lie</button><button class="stop" onclick="act('stop')">STOP</button></div>
 <div class="row"><button class="vol" onclick="post('/api/volume?step=-10')">Vol &minus;</button><button class="vol" onclick="post('/api/volume?step=10')">Vol +</button><button class="vol" onclick="post('/api/volume?mute=toggle')">Mute</button><button onclick="photo(this)">&#128247;</button><button class="rec" id="recb" onclick="recToggle()">&#9210; Rec</button></div></div>
 <div class="card"><h3>Home cameras</h3><div class="row"><button onclick="blink('main door')">&#128682; Main door</button><button onclick="blink('patio')">&#127795; Patio</button></div><div id="blinkbox" style="display:none;margin-top:8px"><img id="blinkimg" style="width:100%;border-radius:12px"><div id="blinkmsg" style="font-size:12px;color:var(--muted);margin-top:4px"></div></div></div>
 <div class="card"><h3>Chat</h3><div id="chat"></div><div id="inrow"><input id="txt" placeholder="Chinnu ki type cheyyi..." autocomplete="off"><button onclick="send()">&#10148;</button></div></div>
</section>
<section class="tab" id="t-ctl">
 <div class="card"><div id="cam"><img id="camimg"><button id="camtg" onclick="camToggle()">&#9654; Camera</button></div>
 <div class="row"><button onclick="act('sit')">Sit</button><button onclick="act('stand')">Stand</button><button onclick="act('lie')">Lie</button><button onclick="act('stretch')">Stretch</button></div>
 <div class="row"><button onclick="act('wag_tail')">Wag</button><button onclick="act('shake_head')">Shake</button><button onclick="act('tilt_head')">Tilt</button><button onclick="photo(this)">&#128247;</button></div></div>
 <div class="card"><h3>Move (hold) <select id="spd" style="float:right"><option value="80">slow</option><option value="98">normal</option><option value="100" selected>fast</option></select></h3><div class="dpad"><div></div><button data-a="step_forward">&#9650;</button><div></div><button data-a="step_left">&#9664;</button><button class="stop" onclick="act('stop');holdStop()">STOP</button><button data-a="step_right">&#9654;</button><div></div><button data-a="step_backward">&#9660;</button><div></div></div></div>
 <div class="card"><h3>Head</h3><label>Yaw<span id="vy">0</span></label><input type="range" id="yaw" min="-90" max="90" value="0"><label>Pitch<span id="vp">0</span></label><input type="range" id="pitch" min="-40" max="30" value="0"><label>Roll<span id="vr">0</span></label><input type="range" id="roll" min="-60" max="60" value="0"><div class="row" style="margin-top:8px"><button onclick="center()">Center head</button></div></div>
</section>
<section class="tab" id="t-lights">
 <div class="card" id="speedcard"><h3>&#128246; Speed regulator <span id="spdsum" style="float:right;text-transform:none;letter-spacing:0"></span></h3>
  <div style="font-size:13px;color:var(--muted);margin-bottom:8px">Works for devices on <b style="color:var(--fg)">Chinnu-Hotspot</b>. Join it with the QR, then pick a speed for each device.</div>
  <div class="row"><button onclick="wpass()" id="wpb">&#128273; Show password</button><button onclick="wqr()">&#128247; Join QR</button></div>
  <div id="wqr" style="display:none;text-align:center;margin:6px 0 10px"><img id="wqrimg" style="width:220px;max-width:80%;border-radius:12px;background:#fff;padding:6px"><div style="font-size:12px;color:var(--muted)">Scan with the other phone's camera &rarr; Join "Chinnu-Hotspot"</div></div>
  <div id="spdlist" style="font-size:14px"></div></div>
 <div class="card"><h3>Govee plugs <button style="float:right;flex:none;padding:2px 10px;font-size:12px" onclick="devices(1)">&#8635;</button></h3><div id="govee" style="font-size:14px;color:var(--muted)">loading...</div></div>
 <div class="card"><h3>Power strip</h3><div id="strip" style="font-size:14px;color:var(--muted)">loading...</div></div>
 <div class="card"><h3>Room (fan)</h3><div class="row"><button class="light" onclick="cmd('morning light')">Morning 40%</button><button class="light" onclick="cmd('full light')">Full 100%</button><button class="light" onclick="cmd('mood light')">Mood 15%</button></div>
 <div class="row"><button class="light" onclick="light('room','on')">On</button><button class="light" onclick="light('room','off')">Off</button></div><label>Brightness<span id="vb">40</span></label><input type="range" id="bri" min="1" max="100" value="40"></div>
 <div class="card"><h3>Desk lamp</h3><div class="row"><button class="light" onclick="light('desk','on')">On</button><button class="light" onclick="light('desk','off')">Off</button></div><label>Brightness<span id="vd">100</span></label><input type="range" id="brid" min="1" max="100" value="100"></div>
 <div class="card"><h3>Wi-Fi devices <span id="wifin" style="text-transform:none;letter-spacing:0"></span> <button style="float:right;flex:none;padding:2px 10px;font-size:12px" onclick="wifi(1)">&#8635; scan</button></h3>
  <div style="font-size:12px;color:var(--muted);margin-bottom:6px">Tap a device to name it. Speed limits work on Chinnu-Hotspot devices &rarr; <a href="/server" style="color:var(--accent)">Server page</a></div>
  <div id="wifi" style="font-size:14px;color:var(--muted)">loading...</div><div class="row" style="margin-top:8px"><button id="wifimore" onclick="wifiAll=!wifiAll;wifi()">Show offline too</button></div></div>
 <div class="card"><h3>Routines</h3><div class="row"><button onclick="cmd('movie mode')">Movie</button><button onclick="cmd('work mode')">Work</button><button onclick="cmd('good night')">Good night</button></div></div>
</section>
<section class="tab" id="t-server">
 <div class="card"><div style="display:flex;align-items:center;gap:12px"><div id="upbig" style="font-size:34px;font-weight:800">–</div><div style="flex:1"><div style="font-weight:600">features running</div><div id="upsub" style="font-size:12px;color:var(--muted)">checking…</div></div><button style="flex:0 0 auto;padding:10px 14px;font-size:14px" id="chkb" onclick="appCheck()">&#8635; Check now</button></div></div>
 <div class="card"><h3>Modes</h3><div id="modes"></div></div>
 <div class="card"><h3>PiDog battery (today) <span id="batnow" style="float:right;text-transform:none;letter-spacing:0"></span></h3><div id="batchart" style="height:70px"></div></div>
 <div id="feats"></div>
 <div class="card"><h3>OpenAI spend</h3><div class="kv" id="spend"></div></div>
 <div class="card"><h3>Server</h3><div class="kv" id="srv"></div></div>
 <div class="card"><h3>Apps &amp; pages</h3>
  <div class="row"><button onclick="location.href='https://chinnu-server.your-tailnet.ts.net'">&#9729; Nextcloud</button><button onclick="location.href='https://chinnu-server.your-tailnet.ts.net:8443'">&#127916; Jellyfin</button></div>
  <div class="row"><button onclick="location.href='/server'">&#128202; Full server page</button><button onclick="location.href='/history'">&#128214; History</button></div>
  <div class="row"><button onclick="location.href='/videos'">&#128252; Gallery</button><button onclick="location.href='/settings'">&#9881; Settings</button><button onclick="location.href='/'">Desk view</button></div></div>
</section>
<section class="tab" id="t-alerts">
 <div class="card"><h3>&#128248; Motion photos <span id="mstat" style="float:right;text-transform:none;letter-spacing:0;font-size:12px"></span></h3>
  <div style="font-size:13px;color:var(--muted);margin-bottom:8px">Chinnu takes a photo + records a 30 s video whenever its camera sees movement. Saved on the server hard disk + Nextcloud (30 days). Tap a tile to play.</div>
  <div class="row"><button id="mon" onclick="motionSet(MS.on?'off':'on')">...</button></div>
  <div style="font-size:12px;color:var(--muted);margin:8px 0 4px">Send to Telegram:</div>
  <div class="row" style="gap:4px"><button id="mt-away" onclick="motionSet('away')">When I'm away</button><button id="mt-always" onclick="motionSet('always')">Always</button><button id="mt-off" onclick="motionSet('never')">Never</button></div>
  <div id="mgrid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px"></div></div>
 <div class="card"><h3>Guard mode</h3><div id="guardbox" style="font-size:14px;color:var(--muted);margin-bottom:8px">…</div>
  <div class="row"><button onclick="modeSet('guard','on')">&#128737; Guard ON</button><button onclick="modeSet('guard','off')">Guard OFF</button></div></div>
 <div class="card"><h3>Home cameras</h3><div id="blinkst" style="font-size:13px;color:var(--muted);margin-bottom:8px">…</div>
  <div class="row"><button onclick="blink2('main door')">&#128682; Main door</button><button onclick="blink2('patio')">&#127795; Patio</button></div>
  <div id="blinkbox2" style="display:none;margin-top:8px"><img id="blinkimg2" style="width:100%;border-radius:12px"><div id="blinkmsg2" style="font-size:12px;color:var(--muted);margin-top:4px"></div></div></div>
 <div class="card"><h3>Reports</h3>
  <div class="row"><button onclick="rep('brief')">&#9728; Morning briefing</button><button onclick="rep('night')">&#127769; Night report</button><button onclick="rep('diary')">&#129504; Diary</button></div>
  <div id="reptxt" style="white-space:pre-wrap;font-size:14px;line-height:1.4;display:none;margin-top:6px"></div>
  <div class="row" id="repsend" style="display:none;margin-top:8px"><button onclick="repSend()">&#128228; Send to Telegram</button></div></div>
 <div class="card"><h3>Alerts &amp; events <select id="adays" style="float:right" onchange="alerts()"><option value="1">today</option><option value="3" selected>3 days</option><option value="7">7 days</option></select></h3><div id="alist" style="font-size:14px"></div></div>
</section>
<div id="dog" style="display:none"></div><div id="svcs" style="display:none"></div>
</main>
<nav><button class="on" onclick="tab('home',this)"><span>&#128054;</span>Chinnu</button><button onclick="tab('ctl',this)"><span>&#127918;</span>Control</button><button onclick="tab('lights',this)"><span>&#127968;</span>Home</button><button onclick="tab('server',this)"><span>&#128200;</span>Status</button><button onclick="tab('alerts',this)"><span>&#128276;</span>Alerts</button></nav>
<script>
async function blink(c){const b=document.getElementById('blinkbox');b.style.display='block';document.getElementById('blinkmsg').textContent=c+': loading (~15 s)...';
try{const r=await fetch('/api/blink/'+encodeURIComponent(c)+'.jpg?t='+Date.now());if(!r.ok)throw new Error(await r.text());const u=URL.createObjectURL(await r.blob());document.getElementById('blinkimg').src=u;document.getElementById('blinkmsg').textContent=(r.headers.get('X-Camera')||c)+' '+new Date().toLocaleTimeString()}catch(e){document.getElementById('blinkmsg').textContent='failed: '+e.message}}
const $=id=>document.getElementById(id);
function tab(n,b){document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));$('t-'+n).classList.add('on');document.querySelectorAll('nav button').forEach(x=>x.classList.remove('on'));b.classList.add('on');if(n==='server')srv();if(n==='lights')devices()}
async function post(u){try{return await (await fetch(u,{method:'POST'})).json()}catch(e){return {ok:false}}}
async function ownGet(){try{const r=await (await fetch('/api/owner')).json();$('own').textContent=r.owner?'\u{1F513} owner':'\u{1F512} GUEST mode ON'}catch(e){}}
async function ownSet(a){await post('/api/owner/'+a);ownGet()}
ownGet();setInterval(ownGet,20000);
async function act(n){$('st').textContent=n+'...';const r=await post('/api/action/'+n);$('st').textContent=r&&r.ok?'ok':'busy'}
function light(n,a){post('/api/light/'+n+'/'+a)}function cmd(n){post('/api/cmd/'+encodeURIComponent(n))}
let bt=null;['bri','brid'].forEach(id=>$(id).addEventListener('input',()=>{const v=$(id).value;$(id==='bri'?'vb':'vd').textContent=v;clearTimeout(bt);bt=setTimeout(()=>post('/api/light/'+(id==='bri'?'room':'desk')+'/brightness?value='+v),250)}));
async function photo(b){const t=b.innerHTML;b.innerHTML='...';const r=await post('/api/photo');b.innerHTML=r.ok?'&#10003;':'&#10007;';setTimeout(()=>b.innerHTML=t,1200)}
let recOn=false;async function recPoll(){try{const s=await (await fetch('/api/record/status')).json();recOn=s.recording;$('recb').innerHTML=recOn?'&#9209; '+s.seconds+'s':'&#9210; Rec';$('recb').style.background=recOn?'#d22':'#5a2030'}catch(e){}}
async function recToggle(){await post(recOn?'/api/record/stop':'/api/record/start');recPoll()}
const MV={step_forward:'forward',step_backward:'backward',step_left:'turn_left',step_right:'turn_right'};let holdT=null,holdA=null;function holdStart(a){holdA=MV[a]||a;fire();holdT=setInterval(fire,300)}async function fire(){if(holdA)post('/api/move/'+holdA+'?speed='+document.getElementById('spd').value)}function holdStop(){clearInterval(holdT);holdT=null;if(holdA)post('/api/move/stop');holdA=null}
document.querySelectorAll('.dpad button[data-a]').forEach(b=>{const a=b.dataset.a;const d=e=>{e.preventDefault();b.classList.add('on');holdStart(a)};const u=()=>{b.classList.remove('on');holdStop()};b.addEventListener('pointerdown',d);b.addEventListener('pointerup',u);b.addEventListener('pointercancel',u);b.addEventListener('pointerleave',u)});
let headT=null;function headSend(){clearTimeout(headT);headT=setTimeout(()=>{const y=$('yaw').value,p=$('pitch').value,r=$('roll').value;$('vy').textContent=y;$('vp').textContent=p;$('vr').textContent=r;post('/api/head?yaw='+y+'&pitch='+p+'&roll='+r)},120)}
['yaw','pitch','roll'].forEach(id=>$(id).addEventListener('input',headSend));function center(){$('yaw').value=0;$('pitch').value=0;$('roll').value=0;headSend()}
let camOn=false;function camToggle(){const im=$('camimg'),c=$('cam'),b=$('camtg');camOn=!camOn;if(camOn){im.src='/camera?'+Date.now();im.style.display='block';c.classList.add('on');b.innerHTML='&#9632; Off'}else{im.src='';im.style.display='none';c.classList.remove('on');b.innerHTML='&#9654; Camera'}}
async function send(){const t=$('txt');const text=t.value.trim();if(!text)return;t.value='';fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,speak:true})}).catch(()=>{})}
$('txt').addEventListener('keydown',e=>{if(e.key==='Enter')send()});
let lastN=0;async function poll(){try{const s=await (await fetch('/api/state')).json();$('dot').className='dot'+(s.robot_ok?' ok':'');$('st').textContent=s.robot_ok?'PiDog online':'PiDog offline';
$('face').className='face '+(s.mode||'idle');$('mode').textContent=(s.mode||'idle')+(s.note?' · '+s.note:'');$('bat').textContent=s.battery&&s.battery.voltage?'\u{1F50B} '+s.battery.percent+'% ('+s.battery.voltage+'V)':'';
if(s.chat&&s.chat.length!==lastN){lastN=s.chat.length;$('chat').innerHTML=s.chat.slice(-30).map(m=>'<div class="msg '+(m.who==='Chinnu'?'chinnu':'chintu')+'"><small>'+m.who+'</small>'+m.text+'</div>').join('');$('chat').scrollTop=1e6}
$('dog').innerHTML='<span>status</span><span>'+(s.robot_ok?'online':'offline')+'</span><span>battery</span><span>'+(s.battery&&s.battery.voltage?s.battery.percent+'% / '+s.battery.voltage+'V':'-')+'</span><span>mode</span><span>'+(s.mode||'')+'</span>'}catch(e){$('st').textContent='server offline';$('dot').className='dot'}}
async function srv(){try{const s=await (await fetch('/api/server')).json();$('srv').innerHTML=['uptime','temp','load','mem','disk','tailscale','time'].map(k=>'<span>'+k+'</span><span>'+(s[k]||'-')+'</span>').join('');
$('svcs').innerHTML=Object.entries(s.services).map(([n,v])=>'<div class="svc"><span class="dot'+(v==='active'?' ok':'')+'"></span><span class="n">'+n+'</span><span style="color:var(--muted);font-size:12px">'+v+'</span><button onclick="post(\'/api/service/'+n+'/restart\').then(srv)">restart</button></div>').join('')}catch(e){}}

let HOME={};const NICE={'chinnu server':'&#128421; Chinnu server','pidog charger':'&#128267; PiDog charger','modem':'&#127760; Modem','router':'&#128246; Router','google tv':'&#128250; Google TV','tv screen':'&#128250; TV','wireless charger':'&#9889; Wireless charger','empty':'(empty)'};
function sw(kind,t,label,on,locked){const btn=locked&&on?'<span style="font-size:12px;color:var(--muted)">&#128274; always on</span>':'<button style="flex:0 0 82px;padding:8px;font-size:14px;background:'+(on?'#1d5a3a':'#2a2f45')+'" onclick="plug(\''+kind+'\',\''+t+'\',\''+(on?'off':'on')+'\',this)">'+(on?'ON':'off')+'</button>';
 return '<div class="svc"><span class="dot'+(on?' ok':'')+'"></span><span class="n">'+label+'</span>'+btn+'</div>'}
async function devices(fresh){try{const s=await (await fetch('/api/home'+(fresh?'?fresh=1':''))).json();HOME=s;const L=new Set(s.locked||[]);let g='';
 if(s.govee){g+='<div class="row" style="margin-bottom:6px"><button onclick="plug(\'govee\',\'tv\',\'on\',this)">&#128250; TV on</button><button onclick="plug(\'govee\',\'tv\',\'off\',this)">TV off</button></div>';
  for(const[dev,st] of Object.entries(s.govee)){for(const[k,v] of Object.entries(st)){if(k==='online'||k==='empty')continue;g+=sw('govee',k,NICE[k]||k,!!v,L.has(k))}}}
 $('govee').innerHTML=g||('error: '+(s.govee_error||'?'));let t='';
 if(s.strip){for(const[k,v] of Object.entries(s.strip)){if(/empty/.test(v.name))continue;t+=sw('strip',k,v.name.replace(/ \(.*\)/,''),v.on,false)}}
 $('strip').innerHTML=t||('error: '+(s.strip_error||'?'))}catch(e){$('govee').textContent='offline'}}
async function plug(kind,t,a,b){if(kind==='strip'&&t==='3'&&a==='off'&&!confirm('Desktop PC power OFF?'))return;if(b)b.textContent='...';const r=await post('/api/plug/'+kind+'/'+encodeURIComponent(t)+'/'+a);if(r&&r.refused&&r.refused.length)alert('Protected: '+r.refused.join(', '));setTimeout(()=>devices(1),800)}
// glasses mode: tap once, talk; Chinnu's answer plays on the phone (-> Bluetooth glasses); keeps listening for follow-ups
let GL=false;try{GL=localStorage.getItem('glasses')==='1'}catch(e){}
const AU=new Audio();AU.playsInline=true;let conv=false;
function glUI(){const b=$('glb');if(!b)return;b.innerHTML=GL?'&#127911; Glasses mode ON &mdash; tap once &amp; talk, answer plays in your glasses':'&#127911; Glasses / phone-speaker mode: off';b.style.background=GL?'#1d5a3a':'';
 $('ptt').innerHTML=GL?'&#127897; Tap to talk (glasses)':'&#127897; Hold to talk (phone mic)';$('pttmsg').textContent=GL?'Tap, speak - Chinnu answers in your glasses and keeps listening. Tap again to stop.':'Hold, speak, release - Chinnu answers out loud'}
function glToggle(){GL=!GL;try{localStorage.setItem('glasses',GL?'1':'0')}catch(e){};glUI()}
async function listenOnce(){
 const st=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
 const mt=MediaRecorder.isTypeSupported('audio/webm')?'audio/webm':'audio/mp4';
 const r=new MediaRecorder(st,{mimeType:mt});const ch=[];r.ondataavailable=x=>ch.push(x.data);
 const ac=new (window.AudioContext||window.webkitAudioContext)();const an=ac.createAnalyser();an.fftSize=1024;ac.createMediaStreamSource(st).connect(an);const buf=new Uint8Array(an.fftSize);
 let spoke=false,last=Date.now();const t0=Date.now();const done=new Promise(res=>{r.onstop=res});
 r.start();$('ptt').style.background='var(--bad)';$('pttmsg').textContent='listening...';
 while(r.state==='recording'){await new Promise(z=>setTimeout(z,100));an.getByteTimeDomainData(buf);let mx=0;for(const v of buf)mx=Math.max(mx,Math.abs(v-128));
  if(mx>14){spoke=true;last=Date.now()}const now=Date.now();
  if(!conv||(spoke&&now-last>1300)||(!spoke&&now-t0>7000)||now-t0>20000)r.stop()}
 await done;st.getTracks().forEach(t=>t.stop());try{ac.close()}catch(e){};$('ptt').style.background='';
 if(!spoke||!conv)return false;
 $('pttmsg').textContent='thinking...';
 try{const x=await (await fetch('/api/voice_reply',{method:'POST',headers:{'Content-Type':mt},body:new Blob(ch,{type:mt})})).json();
  if(!x.text){$('pttmsg').textContent='(nothing heard)';return false}
  $('pttmsg').textContent='\u{1F5E3} '+x.text+'  \u{1F436} '+(x.reply||'');
  if(x.audio){AU.src='data:'+x.mime+';base64,'+x.audio;await AU.play().catch(()=>{});await new Promise(z=>{AU.onended=z;AU.onerror=z;setTimeout(z,90000)})}
  return true}catch(e){$('pttmsg').textContent='failed';return false}}
async function glTap(e){if(e)e.preventDefault();if(conv){conv=false;return}
 conv=true;AU.src='data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=';AU.play().catch(()=>{});
 try{while(conv&&await listenOnce()){}}catch(err){$('pttmsg').textContent='mic blocked: open the https tailscale link'}
 conv=false;$('ptt').style.background=''}
// phone push-to-talk (needs https -> tailscale link)
let rec=null,chunks=[];const P=$('ptt');
async function pttStart(e){if(GL)return glTap(e);e.preventDefault();if(rec)return;try{const st=await navigator.mediaDevices.getUserMedia({audio:true});const mt=MediaRecorder.isTypeSupported('audio/webm')?'audio/webm':'audio/mp4';
 rec=new MediaRecorder(st,{mimeType:mt});chunks=[];rec.ondataavailable=x=>chunks.push(x.data);rec.onstop=async()=>{st.getTracks().forEach(t=>t.stop());const blob=new Blob(chunks,{type:mt});rec=null;$('pttmsg').textContent='sending...';
 try{const r=await (await fetch('/api/voice',{method:'POST',headers:{'Content-Type':mt},body:blob})).json();$('pttmsg').textContent=r.text?'\u{1F5E3} '+r.text:'(nothing heard)'}catch(err){$('pttmsg').textContent='failed'}};
 rec.start();P.style.background='var(--bad)';$('pttmsg').textContent='listening... release to send'}catch(err){$('pttmsg').textContent='mic blocked: open the https tailscale link'}}
function pttStop(){if(GL)return;if(rec&&rec.state==='recording')rec.stop();P.style.background=''}
P.addEventListener('pointerdown',pttStart);P.addEventListener('pointerup',pttStop);P.addEventListener('pointercancel',pttStop);P.addEventListener('pointerleave',pttStop);
// ---------- Status / Alerts tabs (app v2) ----------
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function dur(sec){sec=Math.max(0,Math.round(sec));const d=Math.floor(sec/86400),h=Math.floor(sec%86400/3600),m=Math.floor(sec%3600/60);return d?d+'d '+h+'h':h?h+'h '+m+'m':m+'m'}
const GROUPS_NOTE='Bars = last 24 h (green up, red down)';const GROUPS={core:'Chinnu core',ai:'AI models',home:'Home & network',media:'Media',auto:'Automations'};
let APP=null;
function strip(tl){if(!tl||!tl.length)return '';return '<div style="display:flex;gap:1px;height:10px;margin-top:6px">'+tl.map(v=>'<i style="flex:1;border-radius:1px;background:'+(v==null?'#1b2440':v>=.99?'var(--ok)':v>=.5?'var(--warn)':'var(--bad)')+'"></i>').join('')+'</div>'}
function renderApp(r){APP=r;$('upbig').textContent=r.up+'/'+r.total;$('upbig').style.color=r.up===r.total?'var(--ok)':'var(--warn)';
 $('upsub').textContent='server '+(r.server_up||'').replace('up ','up ')+' · checked every minute';
 const m=r.modes||{};const tg=(name,on,label,extra)=>'<div class="svc"><span class="dot'+(on?' ok':'')+'"></span><span class="n">'+label+(extra?'<div style="font-size:12px;color:var(--muted)">'+esc(extra)+'</div>':'')+'</span><button style="flex:0 0 82px;padding:8px;font-size:14px;background:'+(on?'#1d5a3a':'#2a2f45')+'" onclick="modeSet(\''+name+'\',\''+(on?'off':'on')+'\')">'+(on?'ON':'off')+'</button></div>';
 const ro=(on,label,txt)=>'<div class="svc"><span class="dot'+(on?' ok':'')+'"></span><span class="n">'+label+'</span><span style="font-size:13px;color:var(--muted)">'+esc(txt)+'</span></div>';
 $('modes').innerHTML=tg('guard',m.guard,'&#128737; Guard mode',m.guard_note)+tg('follow',m.follow,'&#128062; Follow me')+tg('saver',m.saver,'&#128176; Saver mode','cheaper models, no realtime voice')+tg('mymodel',m.mymodel,'&#129504; My model (Chinnu-LLM)','your own AI on the server, no GPT bill')+tg('ownvoice',m.ownvoice,'&#128483; Chinnu&#39;s own voice','offline voice (needs the Mac on)')+
  tg('owner',m.owner,'&#128275; Owner mode (its me)',m.owner?'always on - guest only from Hub':'GUEST rules now')+ro(m.presence==='home','&#127968; Presence',m.presence||'not set')+ro(m.quiet,'&#127769; Quiet hours',m.quiet?'on (11 PM-7 AM)':'off')+ro(m.charging,'&#128267; Charger',(m.charging?'charging':'not charging'));
 let h='';for(const[g,gl] of Object.entries(GROUPS)){const fs=r.features.filter(f=>f.group===g);if(!fs.length)continue;const up=fs.filter(f=>f.ok).length;
  h+='<div class="card"><h3>'+gl+(g==='core'?' <span style="text-transform:none;letter-spacing:0;font-size:11px">· bars = last 24 h</span>':'')+' <span style="float:right;color:'+(up===fs.length?'var(--ok)':'var(--warn)')+'">'+up+'/'+fs.length+'</span></h3>';
  for(const f of fs){const since=f.since?(f.ok?'up ':'down ')+dur(r.now-f.since):'';
   h+='<div style="padding:9px 0;border-bottom:1px solid #1b2440"><div style="display:flex;align-items:center;gap:8px"><span class="dot'+(f.ok?' ok':'')+'"></span><span style="flex:1;font-size:15px">'+esc(f.label)+'</span>'+
   (f.restart?'<button style="flex:0 0 auto;padding:6px 10px;font-size:12px" onclick="restartFeat(\''+f.key+'\',\''+esc(f.label)+'\',\''+f.restart+'\',this)">&#8635; restart</button>':'')+'</div>'+
   '<div style="font-size:12px;color:var(--muted);margin-left:18px">'+esc(f.note)+(since?' · '+since:'')+(f.d1!=null?' · 24h '+f.d1+'%':'')+(f.d7!=null?' · 7d '+f.d7+'%':'')+'</div>'+strip(f.tl)+'</div>'}
  h+='</div>'}
 $('feats').innerHTML=h;guardBox()}
async function appLoad(){try{renderApp(await (await fetch('/api/app/features')).json())}catch(e){$('upsub').textContent='could not load'}}
async function appCheck(){const b=$('chkb');b.textContent='checking…';try{renderApp(await (await fetch('/api/app/check',{method:'POST'})).json())}catch(e){}b.innerHTML='&#8635; Check now'}
async function restartFeat(k,label,rs,b){const warn=rs==='pidog'?'\n\nPiDog will be silent for about 1 minute.':rs==='dashboard'?'\n\nThe app reloads in ~15 seconds.':'';
 if(!confirm('Restart '+label+'?'+warn))return;b.textContent='…';const r=await post('/api/app/restart/'+k);b.innerHTML=r&&r.ok?'&#10003;':'&#10007;';
 if(rs==='dashboard')setTimeout(()=>location.reload(),15000);else setTimeout(appLoad,16000)}
async function modeSet(n,a){const u={guard:'/api/guard/'+a,follow:'/api/follow/'+a,saver:'/api/ops/saver/'+a,mymodel:'/api/brain_mode/'+a,ownvoice:'/api/own_voice/'+a,owner:'/api/owner/'+(a==='on'?'unlock':'lock')}[n];
 if(n==='follow'&&a==='on'&&!confirm('Chinnu will walk after you for up to 10 minutes. Start?'))return;await post(u);setTimeout(appLoad,600);if(n==='owner')ownGet()}
async function batChart(){try{const d=await (await fetch('/api/ops/battery')).json();if(!d.length){$('batchart').textContent='no data yet';return}
 const W=320,H=70,n=d.length,x=i=>n<2?W/2:i*(W-4)/(n-1)+2,y=p=>H-4-(p/100)*(H-8);let path=d.map((p,i)=>(i?'L':'M')+x(i).toFixed(1)+' '+y(p.pct).toFixed(1)).join(' ');
 const last=d[n-1];$('batnow').textContent=last.pct+'% · '+last.v+' V'+(last.charging?' · charging':'');
 $('batchart').innerHTML='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%;height:70px"><line x1="0" x2="'+W+'" y1="'+y(20)+'" y2="'+y(20)+'" stroke="#ff5a5f" stroke-dasharray="3 3" stroke-width="1"/><path d="'+path+'" fill="none" stroke="#4cc9f0" stroke-width="2"/></svg><div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted)"><span>'+d[0].t+'</span><span>'+last.t+'</span></div>'}catch(e){}}
async function spend(){try{const b=await (await fetch('/api/ops/budget')).json();$('spend').innerHTML='<span>today</span><span>$'+(b.today||0).toFixed(2)+' of $'+b.limits.daily_usd+'</span><span>this month</span><span>$'+(b.month||0).toFixed(2)+' of $'+b.limits.monthly_usd+'</span><span>saver</span><span>'+(b.saver?'ON':'off')+'</span>'}catch(e){}}
async function srv(){try{const s=await (await fetch('/api/server')).json();$('srv').innerHTML=['uptime','temp','load','mem','disk','tailscale','time'].map(k=>'<span>'+k+'</span><span>'+esc(s[k]||'-')+'</span>').join('')}catch(e){}}
function guardBox(){const m=(APP&&APP.modes)||{};$('guardbox').innerHTML=(m.guard?'<b style="color:var(--ok)">ON</b> · '+esc(m.guard_note||'watching'):'off')+(m.alerts?' · '+m.alerts+' alerts sent':'')+'<br>Turns on by itself when your iPhone leaves home Wi-Fi for 10 min, off when you come back.'}
async function blinkStatus(){try{const r=await (await fetch('/api/blink')).json();$('blinkst').innerHTML=(r.cameras||[]).map(c=>'<span class="dot'+(c.armed?' ok':'')+'"></span> '+esc(c.name)+': '+(c.armed?'armed':'not armed')+', battery '+esc(c.battery)+(c.battery==='low'?' &#9888;':'')).join('<br>')||'no cameras'}catch(e){$('blinkst').textContent='Blink not answering'}}
async function blink2(c){$('blinkbox2').style.display='block';$('blinkmsg2').textContent=c+': loading (~15 s)...';
 try{const r=await fetch('/api/blink/'+encodeURIComponent(c)+'.jpg?t='+Date.now());if(!r.ok)throw new Error(await r.text());$('blinkimg2').src=URL.createObjectURL(await r.blob());$('blinkmsg2').textContent=(r.headers.get('X-Camera')||c)+' '+new Date().toLocaleTimeString()}catch(e){$('blinkmsg2').textContent='failed: '+e.message}}
let REP=null;async function rep(w){REP=w;const t=$('reptxt');t.style.display='block';t.textContent='loading…';$('repsend').style.display='none';
 try{const u={brief:'/api/home_auto/briefing',night:'/api/ops/report',diary:'/api/summary'}[w];const r=await (await fetch(u)).json();t.textContent=r.text||r.summary||'(empty)';if(w!=='diary')$('repsend').style.display='flex'}catch(e){t.textContent='failed'}}
async function repSend(){const u={brief:'/api/home_auto/briefing?send=1',night:'/api/ops/report?send=1'}[REP];if(!u)return;await fetch(u);$('repsend').innerHTML='<button disabled>&#10003; Sent</button>';setTimeout(()=>$('repsend').innerHTML='<button onclick="repSend()">&#128228; Send to Telegram</button>',3000)}
const AICON={alert:'&#9888;',guard:'&#128737;',follow:'&#128062;',charge:'&#128267;',presence:'&#127968;',quiet:'&#127769;',routine:'&#9881;',blink:'&#128247;',face:'&#128100;',door:'&#128682;'};
let MS={};async function motionLoad(){try{MS=await (await fetch('/api/motion')).json();
 $('mstat').textContent=(MS.on?'ON':'off')+' · '+MS.today+' photos, '+(MS.videos_today||0)+' videos today'+(MS.recording?' · \u{1F534} REC':'')+(MS.last_photo?' · last '+MS.last_photo:'');
 $('mon').textContent=MS.on?'\u{1F4F8} Motion photos ON (tap to turn off)':'Motion photos OFF (tap to turn on)';$('mon').style.background=MS.on?'#1d5a3a':'';
 ['away','always','off'].forEach(k=>{$('mt-'+k).style.background=(MS.telegram===k)?'var(--accent)':'';$('mt-'+k).style.color=(MS.telegram===k)?'#000':''});
 const r=await (await fetch('/api/motion/recent?n=12')).json();
 $('mgrid').innerHTML=r.items.length?r.items.map(x=>'<a href="'+(x.video?'/motion/files/'+x.day+'/'+x.video:'/api/motion/img/'+x.day+'/'+x.file)+'" target="_blank" style="text-decoration:none;position:relative;display:block">'+(x.video?'<span style="position:absolute;top:4px;left:4px;background:#000a;color:#fff;border-radius:6px;padding:1px 6px;font-size:11px">&#9654; video</span>':'')+'<img loading="lazy" src="/api/motion/img/'+x.day+'/'+x.file+'" style="width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:8px"><div style="font-size:11px;color:var(--muted);text-align:center">'+x.day.slice(5)+' '+x.t+'</div></a>').join(''):'<div style="grid-column:1/-1;color:var(--muted);font-size:13px">No motion photos yet.</div>'}catch(e){}}
async function motionSet(a){await post('/api/motion/'+a);motionLoad()}
async function alerts(){motionLoad();try{const r=await (await fetch('/api/app/alerts?days='+$('adays').value)).json();let last='';
 $('alist').innerHTML=r.items.map(a=>{let hd='';if(a.day!==last){last=a.day;hd='<div style="font-size:12px;color:var(--muted);margin:10px 0 4px;text-transform:uppercase;letter-spacing:.08em">'+a.day+'</div>'}
  const bad=/DOWN|OFFLINE|fail|seen at home|NOT MOUNTED|evaro/i.test(a.text);
  return hd+'<div style="display:flex;gap:8px;padding:6px 0;border-bottom:1px solid #1b2440"><span style="width:22px">'+(AICON[a.kind]||'&#8226;')+'</span><span style="flex:1;'+(bad?'color:#ff9a9e':'')+'">'+esc(a.text)+'</span><span style="font-size:12px;color:var(--muted)">'+esc(String(a.t).slice(0,5))+'</span></div>'}).join('')||'<span style="color:var(--muted)">No alerts &#127881;</span>'}catch(e){$('alist').textContent='could not load'}}
let wifiAll=false;
async function wifi(scan){try{if(scan)$('wifi').textContent='scanning (~20 s)…';const r=await (await fetch('/api/net/'+(scan?'scan':'devices'),{method:scan?'POST':'GET'})).json();
 $('wifin').textContent='· '+r.online+' online';$('wifimore').textContent=wifiAll?'Hide offline':'Show offline too ('+(r.total-r.online)+')';
 const ds=r.devices.filter(d=>wifiAll||d.online).sort((a,b)=>(b.online-a.online)||((b.label?1:0)-(a.label?1:0))||String(a.label||a.host||a.vendor).localeCompare(String(b.label||b.host||b.vendor)));
 $('wifi').innerHTML=ds.map(d=>'<div class="svc" onclick="labelDev(\''+d.mac+'\',\''+esc(d.label||'').replace(/'/g,'')+'\')"><span class="dot'+(d.online?' ok':'')+'"></span><span class="n">'+esc(d.label||d.host||d.vendor||d.mac)+'<div style="font-size:11px;color:var(--muted)">'+esc(d.ip||'offline')+(d.vendor?' · '+esc(d.vendor):'')+'</div></span><span style="font-size:12px;color:var(--muted)">'+(d.today_min!=null?dur(d.today_min*60)+' today':'')+'</span></div>').join('')}catch(e){$('wifi').textContent='could not load'}}
async function labelDev(mac,cur){const n=prompt('Name for this device ('+mac+'):',cur);if(n===null)return;await fetch('/api/net/label',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mac,label:n.trim()})});wifi()}
function tab(n,b){document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));$('t-'+n).classList.add('on');document.querySelectorAll('nav button').forEach(x=>x.classList.remove('on'));b.classList.add('on');
 if(n==='server'){appLoad();srv();batChart();spend()}if(n==='lights'){devices();wifi();speedLoad()}if(n==='alerts'){appLoad();alerts();blinkStatus()}}
setInterval(()=>{const t=document.querySelector('.tab.on');if(!t||document.hidden)return;if(t.id==='t-server')appLoad();if(t.id==='t-alerts')alerts()},30000);


// ---------- Speed regulator ----------
const SPEEDS=[[0,'&#8734;'],[25,'25'],[10,'10'],[5,'5'],[3,'3'],[1,'1'],[0.5,'½'],[0.25,'¼'],[0.064,'&#9208;']];
let WPW='';
async function wpass(){if(!WPW){try{WPW=(await (await fetch('/api/wifi/clients')).json()).password||''}catch(e){}}
 const b=$('wpb');if(b.dataset.on){b.innerHTML='&#128273; Show password';delete b.dataset.on}else{b.innerHTML=esc(WPW)+' &nbsp;&#128203;';b.dataset.on=1;try{navigator.clipboard.writeText(WPW)}catch(e){}}}
function wqr(){const q=$('wqr');if(q.style.display==='block'){q.style.display='none';return}$('wqrimg').src='/api/wifi/qr.svg?t='+Date.now();q.style.display='block'}
function mb(x){return x==null?'–':x>=10?x.toFixed(0):x.toFixed(1)}
async function speedLoad(){try{const r=await (await fetch('/api/wifi/clients')).json();const ds=r.devices||[];const on=ds.filter(d=>d.online);
 const tot=on.reduce((a,d)=>a+(d.now_down||0),0);$('spdsum').textContent=on.length+' connected · '+mb(tot)+' Mbps now';
 if(!ds.length){$('spdlist').innerHTML='<div style="color:var(--muted);padding:6px 0">Inka evaru Chinnu-Hotspot lo levu. Join QR chupinchi connect cheyinchu.</div>';return}
 $('spdlist').innerHTML=ds.map(d=>{const lim=d.down||0;const nm=esc(d.label||d.mac);
  const chips=SPEEDS.map(([v,l])=>{const sel=(v===0&&!lim)||(v&&Math.abs(lim-v)<0.001);return '<button style="flex:1;padding:8px 0;font-size:13px;'+(sel?'background:var(--accent);color:#000':'')+'" onclick="setSpeed(\''+d.mac+'\','+v+',\''+nm.replace(/'/g,'')+'\')">'+l+'</button>'}).join('');
  return '<div style="padding:10px 0;border-bottom:1px solid #1b2440'+(d.online?'':';opacity:.5')+'"><div style="display:flex;align-items:center;gap:8px"><span class="dot'+(d.online?' ok':'')+'"></span><span style="flex:1" onclick="renameSpd(\''+d.mac+'\',\''+nm.replace(/'/g,'')+'\')">'+nm+' <span style="font-size:11px;color:var(--muted)">&#9998;</span><div style="font-size:11px;color:var(--muted)">'+esc(d.ip||'offline')+(d.mb?' · '+mb(d.mb)+' MB used':'')+'</div></span>'+
   '<span style="text-align:right;font-size:13px">&#8595; '+mb(d.now_down)+' <span style="color:var(--muted)">Mbps</span><br>&#8593; '+mb(d.now_up)+'</span></div>'+
   '<div style="font-size:11px;color:var(--muted);margin:6px 0 4px">Limit (Mbps, &#8734; = none, &#9208; = pause): <b style="color:var(--fg)">'+(lim? (lim<0.1?'paused':lim+' Mbps'):'none')+'</b></div><div class="row" style="gap:4px">'+chips+'</div></div>'}).join('')}catch(e){$('spdlist').textContent='could not load'}}
async function setSpeed(mac,v,nm){if(v&&v<0.1&&!confirm('Pause internet for '+nm+'?'))return;
 await fetch('/api/wifi/limit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mac,down:v,up:v})});speedLoad()}
async function renameSpd(mac,cur){const n=prompt('Name for this device:',cur);if(n===null)return;
 await fetch('/api/wifi/limit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mac,label:n.trim()})});speedLoad()}
setInterval(()=>{const t=document.querySelector('.tab.on');if(t&&t.id==='t-lights'&&!document.hidden)speedLoad()},3000);
async function netg(){try{const r=await (await fetch('/api/netguard')).json();const b=document.getElementById('netban');
 if(r.ok){b.style.display='none';return}
 b.textContent='\u26a0\ufe0f Server internet down since '+r.down_since+' ('+r.down_min+' min). '+(r.cable?'Trying to fix automatically\u2026':'Ethernet cable unplugged \u2014 check the cable!');b.style.display='block'}catch(e){}}
setInterval(netg,30000);netg();glUI();
setInterval(poll,2000);poll();setInterval(recPoll,2000);recPoll();
</script></body></html>"""

_home_cache = {'t': 0, 'data': None}

@router.get('/api/home')
def home_state(fresh: int = 0):
    """Power strip + Govee plug state (cached 15 s; Govee is a cloud API)."""
    import time as _t
    if not fresh and _home_cache['data'] and _t.time() - _home_cache['t'] < 15:
        return _home_cache['data']
    out = {'strip': None, 'govee': None}
    try:
        import tuya_strip; out['strip'] = tuya_strip.status()
    except Exception as e: out['strip_error'] = str(e)[:120]
    try:
        import govee_plug; out['govee'] = govee_plug.status(); out['locked'] = sorted(govee_plug.LOCKED)
    except Exception as e: out['govee_error'] = str(e)[:120]
    _home_cache.update(t=_t.time(), data=out)
    return out

@router.post('/api/plug/{kind}/{target}/{act}')
def plug_set(kind: str, target: str, act: str):
    _home_cache['t'] = 0
    if kind == 'strip':
        import tuya_strip; return tuya_strip.set_outlet(target, act == 'on')
    import govee_plug; return govee_plug.set_plug(target, act == 'on')

@router.post('/api/voice')
async def phone_voice(request: Request):
    """Phone push-to-talk: audio blob -> transcript -> Chinnu answers out loud (and in the chat)."""
    import io, requests as _rq, voice
    body = await request.body()
    ct = request.headers.get('content-type', 'audio/webm')
    ext = 'mp4' if 'mp4' in ct or 'm4a' in ct or 'aac' in ct else ('ogg' if 'ogg' in ct else 'webm')
    if len(body) < 2000: return {'ok': False, 'error': 'too short'}
    f = io.BytesIO(body); f.name = f'phone.{ext}'
    text = voice.client.audio.transcriptions.create(model='gpt-4o-transcribe', file=f, language='te').text.strip()
    if text:
        import threading
        threading.Thread(target=lambda: _rq.post('http://127.0.0.1:8081/chat', json={'text': text, 'speak': True}, timeout=120), daemon=True).start()
    return {'ok': True, 'text': text}

@router.post('/api/voice_reply')
async def phone_voice_reply(request: Request):
    """Glasses / phone mode: audio blob -> transcript -> Chinnu's reply as text + audio, played on the phone
    (so it comes out of Bluetooth glasses/earbuds) instead of the PiDog speaker."""
    import io, base64, asyncio, requests as _rq, voice
    body = await request.body()
    ct = request.headers.get('content-type', 'audio/webm')
    ext = 'mp4' if 'mp4' in ct or 'm4a' in ct or 'aac' in ct else ('ogg' if 'ogg' in ct else 'webm')
    if len(body) < 2000: return {'ok': False, 'error': 'too short', 'text': ''}
    def work():
        f = io.BytesIO(body); f.name = f'phone.{ext}'
        text = voice.client.audio.transcriptions.create(model='gpt-4o-transcribe', file=f, language='te').text.strip()
        if not text: return {'ok': True, 'text': ''}
        try: reply = _rq.post('http://127.0.0.1:8081/chat', json={'text': text, 'speak': False}, timeout=120).json().get('reply') or 'Ok anna'
        except Exception: reply = 'Chinnu busy ga vundi anna, malli try cheyi'
        out = {'ok': True, 'text': text, 'reply': reply}
        try:
            p = voice.tts(reply, '/tmp/chinnu_glasses_tts.wav')
            out.update(audio=base64.b64encode(open(p, 'rb').read()).decode(), mime='audio/wav')
        except Exception as e:
            out['tts_error'] = str(e)
        return out
    return await asyncio.to_thread(work)

@router.get('/m', response_class=HTMLResponse)
def mobile_page():
    return PAGE


@router.get('/api/owner')
def api_owner():
    import owner; return owner.status()

@router.post('/api/owner/{act}')
def api_owner_set(act: str, minutes: int = 30):
    import owner
    return owner.unlock(min(max(minutes, 1), 240), 'phone') if act == 'unlock' else owner.lock()


@router.post('/api/watch')
async def api_watch(request: Request):
    """Apple Watch / Siri Shortcut: {"text": "...", "speak": false} -> plain-text reply.
    The watch is on Chintu's wrist and the URL is tailnet-only, so it runs in owner mode."""
    from fastapi.responses import PlainTextResponse
    import requests as _rq, owner
    try: d = await request.json()
    except Exception: d = {}
    d = {str(k).strip().lower(): v for k, v in (d.items() if isinstance(d, dict) else [])}
    text = str(d.get('text') or next((v for v in d.values() if isinstance(v, str) and v.strip()), '')).strip()
    if not text: return PlainTextResponse('Emi cheppaledu anna')
    owner.unlock(15, 'watch')
    try:
        r = _rq.post('http://127.0.0.1:8081/chat', json={'text': text, 'speak': bool(d.get('speak', True))}, timeout=90).json()
        return PlainTextResponse(r.get('reply') or 'Ok anna')
    except Exception as e:
        return PlainTextResponse('Chinnu busy ga vundi, malli try cheyi')


@router.get('/vr', response_class=HTMLResponse)
def vr_page():
    import pathlib
    return pathlib.Path(__file__).with_name('vr.html').read_text(encoding='utf-8')


# ---------------- Meta glasses (iPhone app "Chinnu Glasses") ----------------
_GPROMPT = 'చిన్ను తో తెలుగు లో మాట్లాడుతున్నారు.'
_WAKE = ('chin', 'innu', 'inu,', 'nnu', 'చిన', 'న్ను', 'చిను')

def _glasses_vision(jpg, question):
    import base64, voice
    b64 = base64.b64encode(jpg).decode()
    r = voice.client.chat.completions.create(model='gpt-4o-mini', max_tokens=160, messages=[
        {'role': 'system', 'content': 'You see through the smart glasses worn by Chintu (the user). Describe concretely and briefly in English what is relevant to his question.'},
        {'role': 'user', 'content': [{'type': 'text', 'text': question or 'What is in front of me?'},
                                     {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64, 'detail': 'low'}}]}])
    return (r.choices[0].message.content or '').strip()

@router.post('/api/glasses/talk')
async def api_glasses_talk(request: Request):
    """multipart: audio (m4a/wav), image (jpeg, optional), wake=1 (ignore unless 'Chinnu' is said).
    Returns audio/wav reply (plays in the glasses) with X-You / X-Reply headers (url-encoded)."""
    import io, time as _t, urllib.parse as up, voice, owner, requests as _rq
    from fastapi.responses import Response, JSONResponse
    form = await request.form()
    audio = form.get('audio'); image = form.get('image')
    if audio is None: return JSONResponse({'ok': False, 'error': 'no audio'}, status_code=400)
    ab = await audio.read()
    open('/tmp/glasses_in.wav', 'wb').write(ab)
    f = io.BytesIO(ab); f.name = getattr(audio, 'filename', None) or 'q.m4a'
    t0 = _t.time()
    text = (voice.client.audio.transcriptions.create(model='gpt-4o-transcribe', file=f, language='te', prompt=_GPROMPT).text or '').strip()
    if text.strip(' .?') == _GPROMPT.strip(' .?'): text = ''
    print(f'[glasses] heard {text!r} ({len(ab)} bytes)', flush=True)
    if not text: return Response(status_code=204)
    if str(form.get('wake', '0')) == '1' and not any(w in text.lower() for w in _WAKE):
        return Response(status_code=204, headers={'X-You': up.quote(text)})
    owner.unlock(15, 'glasses')
    ask = text + '\n[Chintu is talking through his Meta smart glasses, away from the robot - answer short, do not move the robot unless asked. Always call the tools for time, date, weather, news and devices - never reuse an earlier answer.]'
    _words = set(re.findall(r"[a-z]+", text.lower()))
    _see_hit = bool(_words & {'idi', 'idhi', 'chudu', 'chusi', 'see', 'look', 'read', 'chaduvu', 'color', 'rangu', 'kanipistundi', 'kanipisthundi'}) or any(w in text for w in ('ఇది', 'ఇదేంటి', 'చూడు', 'చూసి', 'చూస్', 'కనిపి', 'చదువు', 'రంగు', 'ఎవరు', 'what is this', 'what am i'))
    if image is None and str(form.get('can_see', '0')) == '1' and _see_hit:
        print(f'[glasses] needs camera for {text!r}', flush=True)
        return Response(status_code=409, headers={'X-You': up.quote(text)})
    if image is None and _see_hit:
        ask += '\n[He may be asking about something he is looking at, but the glasses camera is OFF. Do not guess or make up what it is - tell him briefly to turn on the camera switch in the Chinnu app (Chinnu can use the camera when asked) and ask again.]'
    if image is not None:
        try:
            desc = _glasses_vision(await image.read(), text)
            ask += '\n[What his glasses camera sees right now: ' + desc + ']'
        except Exception as e: print('[glasses] vision', e)
    try:
        reply = _rq.post('http://127.0.0.1:8081/chat', json={'text': ask, 'speak': False}, timeout=90).json().get('reply') or 'Sare anna'
    except Exception:
        reply = 'Chinnu busy ga undi anna, malli adugu.'
    path = voice.tts(reply, path=f'/tmp/chinnu_glasses_{int(_t.time() * 1000)}.wav')
    data = open(path, 'rb').read()
    print(f'[glasses] {text!r} -> {reply[:60]!r} ({_t.time() - t0:.1f}s)', flush=True)
    return Response(content=data, media_type='audio/wav',
                    headers={'X-You': up.quote(text), 'X-Reply': up.quote(reply)})
