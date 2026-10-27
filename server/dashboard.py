import threading
#!/usr/bin/env python3
"""Chinnu dashboard: face + state + chat log + touch controls. Runs on the server (port 8080).
The voice agent posts state/chat here; the kiosk display and any browser show it."""
import os, time, json, threading, collections, requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
import yaml
CFG = yaml.safe_load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml'), encoding='utf-8-sig'))
ROBOT = CFG['robot']['url']; HDR = {'x-token': os.environ.get('CHINNU_TOKEN', '')}

app = FastAPI(title='Chinnu Dashboard')

# ---- LAN listener guard (Quest 3 on home Wi-Fi): only allow-listed devices by MAC ----
if os.environ.get('CHINNU_LAN'):
    import json as _j, pathlib as _pl
    _ALLOW = _pl.Path(__file__).with_name('lan_allow.json')
    _PEND = _pl.Path(__file__).with_name('lan_pending.json')
    def _mac(ip):
        try:
            for line in open('/proc/net/arp').read().splitlines()[1:]:
                p = line.split()
                if p[0] == ip: return p[3].lower()
        except Exception: pass
        return ''

    async def _lan_proxy(request):
        from starlette.concurrency import run_in_threadpool
        body = await request.body()
        hdrs = {k: v for k, v in request.headers.items() if k.lower() in ('content-type', 'accept')}
        url = 'http://127.0.0.1:8080' + request.url.path + (('?' + request.url.query) if request.url.query else '')
        try:
            r = await run_in_threadpool(requests.request, request.method, url, data=body or None, headers=hdrs, timeout=150)
        except Exception as e:
            return JSONResponse({'ok': False, 'error': f'main server not answering: {e}'}, status_code=502)
        keep = {k: v for k, v in r.headers.items() if k.lower().startswith('x-') or k.lower() == 'cache-control'}
        return Response(r.content, status_code=r.status_code, media_type=r.headers.get('content-type'), headers=keep)
    @app.middleware('http')
    async def _lan_guard(request, call_next):
        ip = request.client.host if request.client else ''
        mac = _mac(ip)
        try: allow = _j.loads(_ALLOW.read_text())
        except Exception: allow = {}
        if mac and mac in allow:
            if request.url.path.startswith('/api/'):
                return await _lan_proxy(request)
            return await call_next(request)
        try:
            pend = _j.loads(_PEND.read_text()) if _PEND.exists() else {}
            pend[mac or ip] = {'ip': ip, 'ua': request.headers.get('user-agent', '')[:200], 'at': time.strftime('%Y-%m-%d %H:%M:%S')}
            _PEND.write_text(_j.dumps(pend, indent=1))
        except Exception: pass
        return HTMLResponse('<h2 style="font-family:sans-serif">Chinnu: ee device ki permission ledu.</h2>', status_code=403)
state = {'mode': 'idle', 'since': time.time(), 'robot_ok': None, 'note': '', 'battery': None}
chat = collections.deque(maxlen=12)

@app.post('/state')
async def set_state(req: Request):
    d = await req.json()
    if 'mode' in d: state['mode'] = d['mode']; state['since'] = time.time()
    if 'note' in d: state['note'] = d['note']
    if 'chat' in d:
        chat.append({'who': d['chat'].get('who', '?'), 'text': d['chat'].get('text', ''), 'at': time.strftime('%H:%M')})
        history.log('chinnu' if d['chat'].get('who') == 'Chinnu' else 'chintu', d['chat'].get('text', ''))
    return {'ok': True}

@app.get('/api/state')
def get_state():
    if os.environ.get("CHINNU_LAN"):   # LAN copy has no robot poller - ask the main instance
        try: return requests.get("http://127.0.0.1:8080/api/state", timeout=3).json()
        except Exception: pass
    return {'mode': state['mode'], 'age': round(time.time() - state['since'], 1), 'robot_ok': state['robot_ok'], 'battery': state['battery'],
            'note': state['note'], 'chat': list(chat)}

def _robot_poll():
    while True:
        try:
            ok = requests.get(f'{ROBOT}/health', timeout=3).ok
            if state['robot_ok'] is not None and ok != state['robot_ok']: history.log('alert', 'PiDog ' + ('online' if ok else 'OFFLINE'))
            state['robot_ok'] = ok
            try: state['battery'] = requests.get(f'{ROBOT}/battery', headers=HDR, timeout=4).json()
            except Exception: state['battery'] = None
        except Exception:
            state['robot_ok'] = False; state['battery'] = None
        time.sleep(10)
if not os.environ.get('CHINNU_LAN'): threading.Thread(target=_robot_poll, daemon=True).start()
if not os.environ.get('CHINNU_LAN'):
    import autocharge; autocharge.start(ROBOT, HDR)

@app.post('/api/action/{name}')
def action(name: str):
    history.log('action', name)
    try:
        if name == 'stop':
            r = requests.post(f'{ROBOT}/stop', headers=HDR, timeout=5)
        else:
            r = requests.post(f'{ROBOT}/action/{name}', headers=HDR, timeout=20)
        return r.json()
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.get('/api/move/last')
def move_last():
    try: return requests.get(f'{ROBOT}/move/last', headers=HDR, timeout=3).json()
    except Exception as e: return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.post('/api/move/{direction}')
def move(direction: str, ms: int = 700, speed: int = 0):
    """Continuous movement keepalive (remote control hold buttons)."""
    try:
        r = requests.post(f'{ROBOT}/move/{direction}', headers=HDR, params={'ms': ms, 'speed': speed}, timeout=5)
        return r.json()
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.get('/api/govee')
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

@app.get('/api/nextcloud/search')
def nc_search(q: str = ''):
    import nextcloud_sync
    try: return {'q': q, 'results': nextcloud_sync.search(q)}
    except Exception as e: return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.post('/api/nextcloud/sync')
def nc_sync():
    import nextcloud_sync
    try: return {'pushed': nextcloud_sync.sync_dir(REC_DIR)}
    except Exception as e: return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

def _nc_startup_sync():
    try:
        import nextcloud_sync, time as _t; _t.sleep(20)
        n = nextcloud_sync.sync_dir(REC_DIR); print(f'[nextcloud] startup sync pushed {n}', flush=True)
    except Exception as e: print('[nextcloud] startup sync', e, flush=True)
if not os.environ.get('CHINNU_LAN'): threading.Thread(target=_nc_startup_sync, daemon=True).start()

@app.get('/api/strip')
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

@app.post('/api/chat')
async def api_chat(req: Request):
    d = await req.json()
    try:
        r = requests.post('http://127.0.0.1:8081/chat', json={'text': d.get('text', ''), 'speak': d.get('speak', True)}, timeout=120)
        return r.json()
    except Exception as e:
        return JSONResponse({'ok': False, 'error': f'voice agent offline: {e}'}, status_code=500)

@app.post('/api/wake')
def api_wake():
    try:
        r = requests.post(f'{ROBOT}/wake/trigger', headers=HDR, timeout=5)
        return r.json()
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.post('/api/cmd/{name}')
def api_cmd(name: str):
    """Run a commands.yaml routine (used by Alexa/fauxmo and the UI)."""
    history.log('command', name)
    try:
        import commands as custom_cmds
        return custom_cmds.run(name)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

notes = collections.deque(maxlen=50)
@app.post('/api/notify')
async def api_notify(req: Request):
    d = await req.json(); notes.append({'text': d.get('text', ''), 'at': time.time()})
    history.log(d.get('kind', 'notify'), d.get('text', ''))
    return {'ok': True}

@app.get('/api/notify')
def api_notify_list(since: float = 0):
    return [n for n in notes if n['at'] > since]

@app.post('/api/volume')
def volume(req: Request):
    try:
        r = requests.post(f'{ROBOT}/volume', headers=HDR, params=dict(req.query_params), timeout=5)
        return r.json()
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.post('/api/light/{name}/{act}')
def light(name: str, act: str, value: int = None):
    history.log('light', f'{name} {act} {value or ""}'.strip())
    try:
        import home
        return home.light(name, act, value)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.get('/camera')
def camera_proxy():
    def gen():
        try:
            with requests.get(f'{ROBOT}/camera', stream=True, timeout=(5, 30)) as r:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: yield chunk
        except Exception:
            return
    from fastapi.responses import StreamingResponse
    return StreamingResponse(gen(), media_type='multipart/x-mixed-replace; boundary=frame')

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Chinnu</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#0b0f1a;--fg:#e8ecf4;--muted:#8a93a8;--accent:#4cc9f0;--ok:#3ddc84;--warn:#ffb020;--bad:#ff5a5f}
*{box-sizing:border-box;margin:0;padding:0}html,body{height:100%;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;overflow:hidden;user-select:none;cursor:none}
#wrap{display:grid;grid-template-columns:575px minmax(0,1fr);grid-template-rows:minmax(0,1fr) auto auto auto;height:100vh;gap:10px;padding:10px;overflow:hidden}
#left{display:grid;grid-template-rows:110px minmax(0,1fr);}#toprow{display:flex;gap:10px;min-height:0gap:10px;min-height:0;overflow:hidden}
#inrow{grid-column:1/3;display:flex;gap:8px}#inrow input{flex:1;font-size:20px;padding:12px 14px;border-radius:12px;border:0;background:#1b2440;color:var(--fg)}#inrow button{padding:10px 18px}
#kb{grid-column:1/3;display:none;flex-direction:column;gap:6px}#kb.show{display:flex}.krow{display:flex;gap:6px;justify-content:center}.krow button{flex:1;max-width:84px;padding:12px 0;font-size:18px;border-radius:10px;background:#222c4a}.krow button.wide{max-width:none;flex:3}
#right{display:grid;grid-template-rows:auto 1fr;gap:12px;min-height:0}
#cam{background:#000;border-radius:20px;overflow:hidden;position:relative;min-height:0}#cam img{width:100%;height:100%;object-fit:contain;display:block}#cam .lbl{position:absolute;top:8px;left:12px;font-size:13px;color:#cfd6e6;background:rgba(0,0,0,.45);padding:2px 8px;border-radius:8px}
#face{display:flex;flex-direction:column;align-items:center;justify-content:center;background:#10162a;border-radius:20px;position:relative;width:110px;height:110px;flex:none;overflow:hidden}.eyes{height:56px;align-items:center}#info{flex:1;background:#10162a;border-radius:20px;padding:12px 14px;display:flex;flex-direction:column;gap:6px;font-size:15px;color:var(--muted);overflow:hidden}#note{color:var(--fg);font-size:14px;line-height:1.3;overflow:hidden}
.eyes{display:flex;gap:28px}.eye{width:44px;height:44px;background:var(--accent);border-radius:50%;position:relative;transition:all .25s;box-shadow:0 0 40px rgba(76,201,240,.5)}
.eye:after{content:"";position:absolute;width:14px;height:14px;background:#0b0f1a;border-radius:50%;top:15px;left:15px;transition:all .25s}
.idle .eye{animation:blink 5s infinite}.listening .eye{height:52px;background:#3ddc84;box-shadow:0 0 50px rgba(61,220,132,.6)}
.thinking .eye{width:42px;height:24px;border-radius:40%;background:#ffb020;box-shadow:0 0 40px rgba(255,176,32,.5)}.thinking .eye:after{top:5px}
.speaking .eye{animation:bob .4s infinite alternate}.error .eye{background:var(--bad)}.sleep .eye{height:8px;border-radius:10px}.sleep .eye:after{display:none}
@keyframes blink{0%,92%,100%{height:44px}96%{height:5px}}@keyframes bob{from{transform:translateY(0)}to{transform:translateY(-14px)}}
#mouth{margin-top:6px;width:36px;height:8px;border-bottom:4px solid var(--accent);border-radius:0 0 60px 60px;transition:all .25s}
.speaking #mouth{animation:talk .25s infinite alternate}.thinking #mouth{width:30px}.listening #mouth{height:30px;border-radius:0 0 60px 60px}
@keyframes talk{from{height:4px;width:28px}to{height:12px;width:40px}}
#mode{position:absolute;bottom:4px;left:0;right:0;text-align:center;color:var(--muted);font-size:11px;letter-spacing:.08em;text-transform:uppercase}
#status{font-size:15px;color:var(--muted)}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;background:var(--bad)}.dot.ok{background:var(--ok)}
#chat{background:#10162a;border-radius:20px;padding:14px;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end;gap:10px;font-size:19px;line-height:1.35;min-height:0}
.msg{padding:8px 12px;border-radius:12px;max-width:95%}.chintu{background:#1b2440;align-self:flex-end}.chinnu{background:#163a3a;align-self:flex-start}
.msg small{display:block;color:var(--muted);font-size:12px;margin-bottom:2px}
#ctl{grid-column:1/3;display:grid;grid-template-columns:repeat(14,1fr);gap:8px}
button{font-size:18px;padding:16px 4px;border:0;border-radius:14px;background:#1f2a48;color:var(--fg);font-weight:600}button:active{background:var(--accent);color:#000}
button.stop{background:#6b1f24}button.light{background:#3a3516}button.vol{background:#1d3a2a}
#winbar{position:fixed;top:0;right:0;display:flex;gap:4px;z-index:99}#winbar button{width:52px;height:40px;font-size:20px;border:0;border-radius:0 0 0 10px;background:#2a3356;color:#cfd8ff;opacity:.85}#winbar button.x{background:#7a2030}#camtg{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);padding:14px 26px;font-size:20px;border-radius:14px;background:#1f2a48;opacity:.9}#cam.on #camtg{top:auto;bottom:10px;left:auto;right:10px;transform:none;padding:8px 14px;font-size:14px;opacity:.7}</style></head><body><div id="wrap"><div id="winbar"><button onclick="win('minimize')" title="Minimize">&#8212;</button><button onclick="win('maximize')" title="Maximize">&#9633;</button><button class="x" onclick="win('close')" title="Close">&#10005;</button></div>
<div id="left"><div id="toprow"><div id="face" class="idle"><div class="eyes"><div class="eye"></div><div class="eye"></div></div><div id="mouth"></div><div id="mode">idle</div></div>
<div id="info"><div id="status"><span class="dot" id="dot"></span><span id="robot">robot</span></div><div id="note"></div></div></div>
<div id="cam"><img id="camimg" style="display:none"><span class="lbl">Chinnu eyes</span><button id="camtg" onclick="camToggle()">&#9654; Camera</button></div></div>
<div id="chat"></div>
<div id="ctl">
<button onclick="wake()" style="background:#1d3a5a">&#127908; Talk</button><button onclick="act('sit')">Sit</button><button onclick="act('stand')">Stand</button><button onclick="act('wag_tail')">Wag</button><button onclick="act('tilt_head')">Tilt</button>
<button class="stop" onclick="act('stop')">STOP</button><button class="light" onclick="light('Lamp1','on')">Lamp On</button><button class="light" onclick="light('Lamp1','off')">Lamp Off</button><button class="vol" onclick="vol('step=-10')">Vol −</button><button class="vol" onclick="vol('step=10')">Vol +</button><button class="vol" id="mute" onclick="vol('mute=toggle')">Mute</button><button onclick="location.href='/control'">&#127918; Control</button><button id="recb" onclick="recToggle()" style="background:#5a2030">&#9210; Rec</button><button id="phb" onclick="photo()">&#128247;</button>
</div>
<div id="inrow"><input id="txt" placeholder="Chinnu ki type cheyyi..." autocomplete="off"><button onclick="toggleKb()">&#9000;</button><button onclick="send()">Send</button></div>
<div id="kb"></div></div>
<script>async function wake(){try{await fetch('/api/wake',{method:'POST'})}catch(e){}}
let camOn=false;function camToggle(){const im=document.getElementById('camimg'),c=document.getElementById('cam'),b=document.getElementById('camtg');camOn=!camOn;if(camOn){im.src='/camera?'+Date.now();im.style.display='block';c.classList.add('on');b.innerHTML='&#9632; Off'}else{im.src='';im.style.display='none';c.classList.remove('on');b.innerHTML='&#9654; Camera'}}
async function win(a){try{await fetch('/api/win/'+a+'?title='+encodeURIComponent(document.title),{method:'POST'})}catch(e){}}

const ROWS=['1234567890','qwertyuiop','asdfghjkl','zxcvbnm'];
function buildKb(){const kb=document.getElementById('kb');let h=ROWS.map(r=>'<div class="krow">'+[...r].map(c=>'<button onclick="key(\''+c+'\')">'+c+'</button>').join('')+'</div>').join('');
h+='<div class="krow"><button onclick="key(\'BS\')">&#9003;</button><button class="wide" onclick="key(\' \')">space</button><button onclick="key(\',\')">,</button><button onclick="key(\'?\')">?</button><button onclick="send()">&#8629;</button></div>';kb.innerHTML=h}
function key(c){const t=document.getElementById('txt');if(c==='BS'){t.value=t.value.slice(0,-1)}else{t.value+=c}}
function toggleKb(){document.getElementById('kb').classList.toggle('show')}
async function send(){const t=document.getElementById('txt');const text=t.value.trim();if(!text)return;t.value='';document.getElementById('kb').classList.remove('show');
try{await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,speak:true})})}catch(e){}}
document.addEventListener('DOMContentLoaded',()=>{buildKb();document.getElementById('txt').addEventListener('keydown',e=>{if(e.key==='Enter')send()})});
let recOn=false;async function recPoll(){try{const s=await (await fetch('/api/record/status')).json();recOn=s.recording;const b=document.getElementById('recb');if(!b)return;b.innerHTML=recOn?'&#9209; '+s.seconds+'s':'&#9210; Rec';b.style.background=recOn?'#d22':'#5a2030'}catch(e){}}
async function photo(){const b=document.getElementById('phb')||document.querySelector('button[onclick="photo()"]');const t=b.innerHTML;b.innerHTML='...';try{const r=await (await fetch('/api/photo',{method:'POST'})).json();b.innerHTML=r.ok?'&#10003;':'&#10007;'}catch(e){b.innerHTML='&#10007;'}setTimeout(()=>b.innerHTML=t,1200)}
async function recToggle(){await fetch(recOn?'/api/record/stop':'/api/record/start',{method:'POST'});recPoll()}
setInterval(recPoll,1000);recPoll();
async function act(n){fetch('/api/action/'+n,{method:'POST'})}
async function vol(q){const r=await (await fetch('/api/volume?'+q,{method:'POST'})).json();document.getElementById('mute').textContent=r.muted?'Unmute':'Mute '+(r.percent??'')+'%'}
async function light(n,a){fetch('/api/light/'+encodeURIComponent(n)+'/'+a,{method:'POST'})}
const esc=s=>s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
async function tick(){try{const s=await (await fetch('/api/state')).json();
const f=document.getElementById('face');f.className=s.mode||'idle';document.getElementById('mode').textContent=(s.mode||'idle');document.getElementById('note').textContent=s.note||'';
document.getElementById('dot').className='dot'+(s.robot_ok?' ok':'');document.getElementById('robot').textContent=(s.robot_ok?'PiDog online':'PiDog offline')+(s.battery&&s.battery.voltage?'  \u{1F50B} '+s.battery.percent+'% ('+s.battery.voltage+'V)':'');
document.getElementById('chat').innerHTML=s.chat.slice(-4).map(m=>`<div class="msg ${m.who==='Chinnu'?'chinnu':'chintu'}"><small>${m.who} · ${m.at}</small>${esc(m.text)}</div>`).join('');}catch(e){}}
setInterval(tick,1000);tick();
</script></body></html>"""

@app.get('/', response_class=HTMLResponse)
def index():
    return PAGE

# ------------------------------------------------------------------ manual controller page
@app.post('/api/head')
def api_head(req: Request):
    try:
        r = requests.post(f'{ROBOT}/head', headers=HDR, params=dict(req.query_params), timeout=8)
        return r.json()
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

CONTROL = r"""<!doctype html><html><head><meta charset="utf-8"><title>Chinnu Controller</title>
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<style>
:root{--bg:#0b0f1a;--fg:#e8ecf4;--muted:#8a93a8;--accent:#4cc9f0;--bad:#ff5a5f}
*{box-sizing:border-box;margin:0;padding:0}html,body{height:100%;background:var(--bg);color:var(--fg);font-family:system-ui,sans-serif;user-select:none;-webkit-user-select:none;touch-action:manipulation;overflow:hidden}
#wrap{display:grid;grid-template-columns:1fr 1.1fr 1fr;grid-template-rows:auto 1fr;height:100vh;gap:10px;padding:10px}
#top{grid-column:1/4;display:flex;align-items:center;gap:12px}#top a{color:var(--accent);text-decoration:none;font-size:18px}#top .st{color:var(--muted);font-size:14px;margin-left:auto}
.panel{background:#10162a;border-radius:18px;padding:12px;display:flex;flex-direction:column;gap:10px;min-height:0}
#cam{background:#000;border-radius:14px;overflow:hidden;aspect-ratio:16/9}#cam img{width:100%;height:100%;object-fit:cover;display:block}
.dpad{display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(3,1fr);gap:8px;flex:1;min-height:220px}
.dpad button{font-size:34px;border:0;border-radius:16px;background:#1f2a48;color:var(--fg)}.dpad button:active,.dpad button.on{background:var(--accent);color:#000}
.dpad .stop{background:#6b1f24;font-size:20px;font-weight:700}
.row{display:flex;gap:8px}.row button{flex:1;font-size:18px;padding:14px 4px;border:0;border-radius:12px;background:#1f2a48;color:var(--fg);font-weight:600}.row button:active{background:var(--accent);color:#000}
label{font-size:14px;color:var(--muted);display:flex;justify-content:space-between}
input[type=range]{width:100%;height:44px;accent-color:var(--accent)}
h3{font-size:15px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase}
#winbar{position:fixed;top:0;right:0;display:flex;gap:4px;z-index:99}#winbar button{width:52px;height:40px;font-size:20px;border:0;border-radius:0 0 0 10px;background:#2a3356;color:#cfd8ff;opacity:.85}#winbar button.x{background:#7a2030}</style></head><body><div id="wrap"><div id="winbar"><button onclick="win('minimize')" title="Minimize">&#8212;</button><button onclick="win('maximize')" title="Maximize">&#9633;</button><button class="x" onclick="win('close')" title="Close">&#10005;</button></div>
<div id="top"><a href="/">&larr; Chinnu</a><h3>Manual controller</h3><span class="st" id="st">ready</span></div>
<div class="panel"><div id="cam"><img src="/camera" onerror="this.style.display='none'"></div>
<div class="row"><button onclick="photo()">&#128247; Photo</button><button id="recb" onclick="recToggle()" style="background:#5a2030">&#9210; Record</button><button onclick="location.href='/videos'">&#128252; Videos</button></div>
<h3>Body</h3><div class="row"><button onclick="act('sit')">Sit</button><button onclick="act('stand')">Stand</button><button onclick="act('lie')">Lie</button><button onclick="act('stretch')">Stretch</button></div>
<div class="row"><button onclick="act('wag_tail')">Wag</button><button onclick="act('shake_head')">Shake</button><button onclick="act('tilt_head')">Tilt</button></div></div>
<div class="panel"><h3>Move (hold to keep going)</h3><div class="dpad">
<div></div><button data-a="step_forward">&#9650;</button><div></div>
<button data-a="step_left">&#9664;</button><button class="stop" onclick="stop()">STOP</button><button data-a="step_right">&#9654;</button>
<div></div><button data-a="step_backward">&#9660;</button><div></div></div></div>
<div class="panel"><h3>Head</h3>
<label>Yaw (left / right)<span id="vy">0</span></label><input type="range" id="yaw" min="-90" max="90" value="0">
<label>Pitch (down / up)<span id="vp">0</span></label><input type="range" id="pitch" min="-40" max="30" value="0">
<label>Roll (tilt)<span id="vr">0</span></label><input type="range" id="roll" min="-60" max="60" value="0">
<div class="row"><button onclick="center()">Center head</button></div></div>
</div>
<script>async function win(a){try{await fetch('/api/win/'+a+'?title='+encodeURIComponent(document.title),{method:'POST'})}catch(e){}}

const st=document.getElementById('st');
let recOn=false;async function recPoll(){try{const s=await (await fetch('/api/record/status')).json();recOn=s.recording;const b=document.getElementById('recb');b.innerHTML=recOn?'&#9209; Stop REC '+s.seconds+'s':'&#9210; Record';b.style.background=recOn?'#d22':'#5a2030'}catch(e){}}
async function photo(){const b=document.getElementById('phb')||document.querySelector('button[onclick="photo()"]');const t=b.innerHTML;b.innerHTML='...';try{const r=await (await fetch('/api/photo',{method:'POST'})).json();b.innerHTML=r.ok?'&#10003;':'&#10007;'}catch(e){b.innerHTML='&#10007;'}setTimeout(()=>b.innerHTML=t,1200)}
async function recToggle(){await fetch(recOn?'/api/record/stop':'/api/record/start',{method:'POST'});recPoll()}
setInterval(recPoll,1000);recPoll();
async function act(n){st.textContent=n+'...';const r=await fetch('/api/action/'+n,{method:'POST'});st.textContent=(await r.json()).ok?'ok':'busy'}
async function stop(){await fetch('/api/action/stop',{method:'POST'});st.textContent='stopped';holdStop()}
let holdT=null,holdA=null;
const MV={step_forward:'forward',step_backward:'backward',step_left:'turn_left',step_right:'turn_right'};function holdStart(a){holdA=MV[a]||a;fire();holdT=setInterval(fire,300)}
async function fire(){if(!holdA)return;try{await fetch('/api/move/'+holdA,{method:'POST'})}catch(e){}}
function holdStop(){clearInterval(holdT);holdT=null;if(holdA)fetch('/api/move/stop',{method:'POST'});holdA=null}
document.querySelectorAll('.dpad button[data-a]').forEach(b=>{
 const a=b.dataset.a;const down=e=>{e.preventDefault();b.classList.add('on');holdStart(a)};const up=e=>{b.classList.remove('on');holdStop()};
 b.addEventListener('pointerdown',down);b.addEventListener('pointerup',up);b.addEventListener('pointercancel',up);b.addEventListener('pointerleave',up);});
let headT=null;function headSend(){clearTimeout(headT);headT=setTimeout(async()=>{const y=yaw.value,p=pitch.value,r=roll.value;vy.textContent=y;vp.textContent=p;vr.textContent=r;try{await fetch(`/api/head?yaw=${y}&pitch=${p}&roll=${r}`,{method:'POST'})}catch(e){}},120)}
['yaw','pitch','roll'].forEach(id=>document.getElementById(id).addEventListener('input',headSend));
function center(){yaw.value=0;pitch.value=0;roll.value=0;headSend()}
</script></body></html>"""


# ---------- video recording ----------
import subprocess, signal, pathlib
from fastapi.staticfiles import StaticFiles
REC_DIR = pathlib.Path.home() / 'chinnu-videos'; REC_DIR.mkdir(exist_ok=True)
rec = {'proc': None, 'file': None, 'started': 0}
rec_lock = threading.Lock()
app.mount('/videos/files', StaticFiles(directory=str(REC_DIR)), name='videos')

def _rec_alive():
    return rec['proc'] is not None and rec['proc'].poll() is None

@app.get('/api/record/status')
def rec_status():
    alive = _rec_alive()
    return {'recording': alive, 'file': rec['file'] if alive else None,
            'seconds': int(time.time() - rec['started']) if alive else 0}

@app.post('/api/record/start')
def rec_start():
    with rec_lock:
        if _rec_alive():
            return {'ok': True, 'already': True, 'file': rec['file']}
        name = time.strftime('chinnu_%Y%m%d_%H%M%S.mp4')
        out = REC_DIR / name
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'mjpeg', '-r', '8', '-i', f'{ROBOT}/camera',
               '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28', '-pix_fmt', 'yuv420p', '-r', '8',
               '-movflags', '+faststart', str(out)]
        try:
            rec['proc'] = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)
        rec['file'] = name; rec['started'] = time.time()
        history.log('record', 'start ' + name)
        return {'ok': True, 'file': name}

@app.post('/api/record/stop')
def rec_stop():
    with rec_lock:
        p = rec['proc']
        if not _rec_alive():
            return {'ok': True, 'recording': False}
        try:
            p.stdin.write(b'q'); p.stdin.flush()
            p.wait(timeout=8)
        except Exception:
            p.send_signal(signal.SIGINT)
            try: p.wait(timeout=5)
            except Exception: p.kill()
        f = rec['file']; rec['proc'] = None
        try:
            import nextcloud_sync; nextcloud_sync.push_async(REC_DIR / f)
        except Exception as e: print('[nextcloud]', e)
        return {'ok': True, 'recording': False, 'file': f}


@app.get('/api/snap')
def api_snap():
    try:
        r = requests.get(f'{ROBOT}/snap.jpg', headers=HDR, timeout=8)
        return Response(content=r.content, media_type='image/jpeg') if r.ok else JSONResponse({'ok': False}, status_code=500)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.get('/api/blink')
def api_blink_list():
    import blink_tool
    try: return {'ok': True, 'cameras': blink_tool.cameras()}
    except Exception as e: return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.get('/api/blink/{name}.jpg')
async def api_blink_snap(name: str):
    """Fresh snapshot from a Blink camera (takes ~10-20 s)."""
    import blink_tool, asyncio
    loop = asyncio.get_running_loop()
    try:
        cam, jpg = await loop.run_in_executor(None, blink_tool.snapshot, name)
        history.log('blink', cam)
        return Response(content=jpg, media_type='image/jpeg', headers={'X-Camera': cam, 'Cache-Control': 'no-store'})
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.get('/api/faces')
def api_faces():
    import faces
    return {'ok': True, 'people': faces.people()}

@app.post('/api/faces/enroll')
async def api_faces_enroll(req: Request, name: str):
    """Body = raw JPEG/PNG bytes (phone upload). Enrols the largest face."""
    import faces
    data = await req.body()
    try:
        r = faces.enroll(name, data)
        if r.get('ok'): history.log('face', f'enrolled {name} ({r["count"]})')
        return r
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)

@app.post('/api/faces/enroll_cam')
def api_faces_enroll_cam(name: str):
    """Enrol from the robot camera right now."""
    import faces
    try:
        r = requests.get(f'{ROBOT}/snap.jpg', headers=HDR, timeout=8)
        res = faces.enroll(name, r.content)
        if res.get('ok'): history.log('face', f'enrolled {name} from camera ({res["count"]})')
        return res
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)

@app.get('/api/faces/identify')
def api_faces_identify():
    import faces
    try:
        r = requests.get(f'{ROBOT}/snap.jpg', headers=HDR, timeout=8)
        return faces.identify(r.content)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)

@app.post('/api/faces/forget')
def api_faces_forget(name: str):
    import faces
    history.log('face', f'forgot {name}')
    return faces.forget(name)

@app.post('/api/photo')
def take_photo():
    try:
        r = requests.get(f'{ROBOT}/snap.jpg', headers=HDR, timeout=8)
        if not r.ok or len(r.content) < 1000:
            return JSONResponse({'ok': False, 'error': f'camera {r.status_code}'}, status_code=500)
        name = time.strftime('chinnu_%Y%m%d_%H%M%S.jpg')
        (REC_DIR / name).write_bytes(r.content)
        history.log('photo', name)
        try:
            import nextcloud_sync; nextcloud_sync.push_async(REC_DIR / name)
        except Exception as e: print('[nextcloud]', e)
        return {'ok': True, 'file': name}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.post('/api/record/delete/{name}')
def rec_delete(name: str):
    f = REC_DIR / pathlib.Path(name).name
    if f.suffix in ('.mp4', '.jpg') and f.exists(): f.unlink()
    return {'ok': True}

@app.get('/videos', response_class=HTMLResponse)
def videos_page():
    files = sorted(list(REC_DIR.glob('*.mp4')) + list(REC_DIR.glob('*.jpg')), key=lambda f: f.stat().st_mtime, reverse=True)
    items = ''.join(
        '<div class="v">' + (f'<video controls preload="metadata" src="/videos/files/{f.name}"></video>' if f.suffix == '.mp4'
                             else f'<a href="/videos/files/{f.name}" target="_blank"><img src="/videos/files/{f.name}" style="width:100%;border-radius:8px"></a>') +
        f'<div class="meta"><span>{f.name}</span><span>{f.stat().st_size//1024} KB</span>'
        f'<a href="/videos/files/{f.name}" download>Download</a>'
        f'<button onclick="del(\'{f.name}\')">Delete</button></div></div>' for f in files) or '<p>Inka videos levu.</p>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Chinnu videos</title>
<style>body{{margin:0;background:#0b0f1a;color:#e6ecff;font-family:system-ui;padding:12px}}a{{color:#7cf}}
#top{{display:flex;gap:16px;align-items:center;margin-bottom:12px}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}}
.v{{background:#121a30;border-radius:12px;padding:8px}}video{{width:100%;border-radius:8px;background:#000}}
.meta{{display:flex;gap:10px;align-items:center;font-size:13px;color:#9fb0d0;margin-top:6px;flex-wrap:wrap}}
button{{padding:6px 12px;border:0;border-radius:8px;background:#5a2030;color:#fff}}</style></head><body>
<div id="top"><a href="/">&larr; Chinnu</a><a href="/control">Control</a><h3 style="margin:0">Gallery ({len(files)})</h3></div>
<div class="grid">{items}</div>
<script>async function del(n){{if(!confirm('Delete '+n+'?'))return;await fetch('/api/record/delete/'+n,{{method:'POST'}});location.reload()}}</script>
</body></html>"""


# ---------- window controls for the touch display (labwc titlebar buttons don't take touch) ----------
WL_ENV = dict(os.environ, WAYLAND_DISPLAY='wayland-0', XDG_RUNTIME_DIR='/run/user/1000')
@app.post('/api/win/{action}')
async def win_action(action: str, req: Request):
    if action not in ('minimize', 'maximize', 'close', 'focus'):
        return JSONResponse({'ok': False, 'error': 'bad action'}, status_code=400)
    title = (req.query_params.get('title') or 'Chinnu').strip()
    try:
        r = subprocess.run(['wlrctl', 'toplevel', action, f'title:{title}'], env=WL_ENV, capture_output=True, text=True, timeout=5)
        return {'ok': r.returncode == 0, 'err': r.stderr.strip()}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

import mobile, settings, history
app.include_router(mobile.router)
app.include_router(settings.router)
app.include_router(history.router)

@app.get('/control', response_class=HTMLResponse)
def control():
    return CONTROL


@app.get('/api/autocharge')
def api_autocharge():
    import autocharge; return autocharge.status()


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


import srvpage as _srv
app.include_router(_srv.router)

if not os.environ.get("CHINNU_LAN"):
    import hddwatch; hddwatch.start()

if not os.environ.get('CHINNU_LAN'):
    import netscan; netscan.start()

if not os.environ.get('CHINNU_LAN'):
    import wifishaper; wifishaper.start()
    import nightly; nightly.start()
    import netguard; netguard.start()

if not os.environ.get('CHINNU_LAN'):
    import ops; ops.start(ROBOT, HDR)

@app.get('/api/ops/budget')
def api_ops_budget():
    import ops; return ops.budget_check()

@app.post('/api/ops/saver/{act}')
def api_ops_saver(act: str):
    import ops; ops.set_saver(act == 'on', 'turned on by Chintu' if act == 'on' else ''); return {'saver': ops.saver_on()}

@app.get('/api/ops/battery')
def api_ops_battery(day: str = None):
    import ops; return ops.battery_series(day)

@app.get('/api/ops/report')
def api_ops_report(send: int = 0):
    import ops
    t = ops.report_text()
    if send: ops.tg(t)
    return {'text': t}

if not os.environ.get('CHINNU_LAN'):
    import home_auto; home_auto.start(ROBOT, HDR)
    import motioncam; motioncam.start(ROBOT, HDR)

@app.get('/api/home_auto')
def api_home_auto():
    import home_auto; return home_auto.status()

@app.get('/api/home_auto/briefing')
def api_briefing(send: int = 0):
    import home_auto; t = home_auto.briefing_text()
    if send: home_auto.tg(t)
    return {'text': t}


import uptime as _up
app.include_router(_up.router)
if not os.environ.get('CHINNU_LAN'):
    _up.start(ROBOT, HDR)


@app.get('/api/brain_mode')
def api_brain_mode():
    import chinnu_llm; return chinnu_llm.status()

@app.post('/api/brain_mode/{act}')
def api_brain_mode_set(act: str):
    import chinnu_llm
    if act == 'on' and not chinnu_llm.available():
        return JSONResponse({'ok': False, 'error': 'chinnu:3b model not installed in Ollama'}, status_code=400)
    chinnu_llm.set_mode('chinnu' if act == 'on' else 'gpt')
    try:
        import history; history.log('alert', 'Brain: ' + ('Chinnu-LLM (my model)' if act == 'on' else 'GPT-4.1'))
    except Exception: pass
    return chinnu_llm.status()


if not os.environ.get('CHINNU_LAN'):
    import vision_plus; vision_plus.start()

@app.get('/api/vision_plus')
def api_vision_plus():
    import vision_plus; return vision_plus.status()

@app.post('/api/vision_plus/find')
def api_vp_find(name: str):
    import vision_plus; return vision_plus.find_object(name)


@app.get('/api/own_voice')
def api_own_voice():
    import voice
    try: mac = requests.get(voice.LOCAL_SPEECH + '/health', timeout=2).json()
    except Exception: mac = {}
    return {'on': voice.own_voice_on(), 'ready': bool(mac.get('tts_ready')), 'stt_on_mac': bool(mac.get('stt_ready'))}

@app.post('/api/own_voice/{act}')
def api_own_voice_set(act: str):
    import voice; voice.set_own_voice(act == 'on'); return api_own_voice()


@app.get('/api/netguard')
def api_netguard():
    import netguard; return netguard.status()


@app.get('/api/motion')
def api_motion():
    import motioncam; return motioncam.status()

@app.post('/api/motion/{act}')
def api_motion_set(act: str):
    import motioncam
    if act in ('on', 'off'): return motioncam.set_cfg(on=(act == 'on'))
    if act in ('away', 'always', 'never'): return motioncam.set_cfg(telegram='off' if act == 'never' else act)
    return {'ok': False}

@app.get('/api/motion/recent')
def api_motion_recent(n: int = 12):
    import motioncam; return {'items': motioncam.recent(min(n, 60))}

@app.get('/api/motion/img/{day}/{file}')
def api_motion_img(day: str, file: str):
    import motioncam
    from fastapi.responses import Response
    b = motioncam.image(day, file)
    return Response(b, media_type='image/jpeg') if b else Response(status_code=404)


# motion clips (mp4) served with range support so iPhone Safari can play them
try:
    from fastapi.staticfiles import StaticFiles as _SF
    import pathlib as _pl
    _pl.Path('/mnt/hdd/chinnu/motion').mkdir(parents=True, exist_ok=True)
    app.mount('/motion/files', _SF(directory='/mnt/hdd/chinnu/motion'), name='motionfiles')
except Exception as _e: print('[motion] mount', _e)
