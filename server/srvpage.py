"""/server page: model + service status, restart buttons, device usage timeline, OpenAI usage estimate, suggestions."""
import os, json, time, subprocess, glob, requests
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
BASE = os.path.dirname(os.path.abspath(__file__))
SERVICES = {'voice': 'chinnu-voice', 'dashboard': 'chinnu-dashboard', 'lan': 'chinnu-lan', 'telegram': 'chinnu-telegram',
            'alexa': 'chinnu-alexa'}
CONTAINERS = {'ollama': 'ollama', 'jellyfin': 'jellyfin', 'nextcloud': 'nextcloud-app-1'}

def _sh(cmd, t=8):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=t).stdout.strip()
    except Exception as e: return f'err {e}'

def _check(fn):
    t0 = time.time()
    try:
        ok, note = fn()
    except Exception as e:
        ok, note = False, str(e)[:120]
    return {'ok': ok, 'note': note, 'ms': int((time.time() - t0) * 1000)}

@router.get('/api/srv/status')
def srv_status():
    import yaml
    cfg = yaml.safe_load(open(os.path.join(BASE, 'config.yaml'), encoding='utf-8-sig')) or {}
    V = cfg.get('voice') or {}
    robot = (cfg.get('robot') or {}).get('url', 'http://192.168.1.208:8090'); hdr = {'x-token': os.environ.get('CHINNU_TOKEN', '')}
    def openai_model(m):
        def f():
            import voice
            voice.client.models.retrieve(m); return True, 'reachable'
        return f
    def ollama():
        r = requests.get('http://127.0.0.1:11434/api/tags', timeout=4).json()
        names = [x['name'] for x in r.get('models', [])]
        want = (cfg.get('local_llm') or {}).get('model', 'qwen2.5:3b')
        return (want in names or any(n.startswith(want) for n in names)), ', '.join(names) or 'no models pulled'
    def robot_h():
        h = requests.get(f'{robot}/health', headers=hdr, timeout=4).json()
        b = requests.get(f'{robot}/battery', headers=hdr, timeout=4).json()
        return True, f"wake word: {h.get('kws')}, battery {b.get('percent')}% ({b.get('voltage')} V)"
    def local_file(p, label):
        def f():
            ok = os.path.exists(os.path.join(BASE, p)); return ok, label if ok else f'{p} missing'
        return f
    def credits():
        import voice
        try:
            voice.client.chat.completions.create(model='gpt-4o-mini', messages=[{'role': 'user', 'content': 'ok'}], max_tokens=1)
            return True, 'API key works, credits available'
        except Exception as e:
            m = str(e); return False, 'NO CREDITS - add at platform.openai.com' if 'quota' in m or 'credit' in m else m[:100]
    models = [
        ('OpenAI credits', credits),
        (f"Realtime voice ({V.get('realtime_model', 'gpt-realtime')})", openai_model(V.get('realtime_model', 'gpt-realtime'))),
        (f"Brain ({(cfg.get('brain') or {}).get('model') or 'gpt-4.1'})", openai_model('gpt-4.1')),
        (f"Speech-to-text ({V.get('stt_model', 'gpt-4o-transcribe')})", openai_model(V.get('stt_model', 'gpt-4o-transcribe'))),
        (f"Text-to-speech ({V.get('tts_model', 'gpt-4o-mini-tts')})", openai_model(V.get('tts_model', 'gpt-4o-mini-tts'))),
        ('Ollama local brain', ollama),
        ('PiDog body + wake word', robot_h),
        ('YOLO objects (local)', local_file('models/yolo11n.onnx', 'yolo11n, on server')),
        ('Face ID (local)', local_file('faces.json', 'faces enrolled')),
        ('Voice ID (local)', local_file('voices.json', 'voice enrolled')),
    ]
    out_models = [{'name': n, **_check(f)} for n, f in models]
    def since_unit(u):
        t = _sh(['systemctl', 'show', u, '-p', 'ActiveEnterTimestamp', '--value'])
        return t.split(' ', 1)[1].rsplit(' ', 1)[0] if t and ' ' in t else ''
    svcs = [{'name': k, 'unit': u, 'state': _sh(['systemctl', 'is-active', u]), 'since': since_unit(u)} for k, u in SERVICES.items()]
    dps = _sh(['docker', 'ps', '-a', '--format', '{{.Names}}|{{.Status}}'])
    cont = []
    for k, c in CONTAINERS.items():
        st = next((l.split('|', 1)[1] for l in dps.splitlines() if l.split('|')[0] == c), 'not found')
        cont.append({'name': k, 'unit': c, 'state': 'active' if st.startswith('Up') else st, 'since': st.replace('Up ', 'up ') if st.startswith('Up') else ''})
    sysinfo = {'temp': _sh(['vcgencmd', 'measure_temp']).replace('temp=', ''), 'uptime': _sh(['uptime', '-p']),
               'disk': _sh(['sh', '-c', "df -h / | awk 'NR==2{print $5\" used of \"$2}'"]),
               'hdd': (_sh(['sh', '-c', "df -h /mnt/hdd | awk 'NR==2{print $5\" used of \"$2}'"]) if subprocess.run(['findmnt', '/mnt/hdd'], capture_output=True).returncode == 0 else 'NOT MOUNTED - Nextcloud/Jellyfin stopped'),
               'ram': _sh(['sh', '-c', "free -h | awk 'NR==2{print $3\" / \"$2}'"])}
    return {'models': out_models, 'services': svcs + cont, 'system': sysinfo, 'at': time.strftime('%H:%M:%S')}

@router.post('/api/srv/restart/{name}')
def srv_restart(name: str):
    if name in SERVICES:
        u = SERVICES[name]
        if name == 'dashboard':      # restart ourselves after replying
            subprocess.Popen(['sh', '-c', f'sleep 1; sudo -n systemctl restart {u}'])
            return {'ok': True, 'note': 'dashboard restarting - page reloads in ~10 s'}
        r = subprocess.run(['sudo', '-n', 'systemctl', 'restart', u], capture_output=True, text=True, timeout=60)
        return {'ok': r.returncode == 0, 'note': r.stderr.strip()[:200] or f'{u} restarted'}
    if name in CONTAINERS:
        r = subprocess.run(['docker', 'restart', CONTAINERS[name]], capture_output=True, text=True, timeout=90)
        return {'ok': r.returncode == 0, 'note': (r.stderr or r.stdout).strip()[:200]}
    if name == 'pidog':
        try: return requests.post('http://127.0.0.1:8080/api/robot/restart', timeout=60).json()
        except Exception as e: return {'ok': False, 'note': str(e)}
    return JSONResponse({'ok': False, 'note': 'unknown'}, status_code=400)

def _events(day):
    p = os.path.join(BASE, 'logs', f'chinnu-{day}.jsonl'); ev = []
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            try: d = json.loads(line)
            except Exception: continue
            if d.get('kind') in ('device', 'light', 'charge', 'guard', 'follow', 'routine', 'alert'): ev.append(d)
    return ev

@router.get('/api/srv/devices')
def srv_devices(day: str = None):
    day = day or time.strftime('%Y-%m-%d')
    ev = _events(day)
    # on-time per device from ON/OFF pairs (device events only)
    on_since, total, switches = {}, {}, {}
    def secs(t): h, m, s = map(int, t.split(':')); return h * 3600 + m * 60 + s
    for d in ev:
        if d.get('kind') != 'device' or 'device' not in d: continue
        name = d['device'].split(' ')[0] if d['device'].startswith('light') else d['device']
        name = d['device'] if not d['device'].startswith('light') else ' '.join(d['device'].split(' ')[:2])
        switches[name] = switches.get(name, 0) + 1
        if d.get('on'): on_since.setdefault(name, secs(d['t']))
        elif name in on_since: total[name] = total.get(name, 0) + secs(d['t']) - on_since.pop(name)
    end = secs(time.strftime('%H:%M:%S')) if day == time.strftime('%Y-%m-%d') else 86400
    for n, s in on_since.items(): total[n] = total.get(n, 0) + end - s
    rows = [{'device': n, 'switches': switches.get(n, 0), 'on_minutes': round(total.get(n, 0) / 60), 'on_now': n in on_since}
            for n in sorted(switches)]
    days = sorted({os.path.basename(p)[7:17] for p in glob.glob(os.path.join(BASE, 'logs', 'chinnu-*.jsonl'))}, reverse=True)[:14]
    return {'day': day, 'days': days, 'devices': rows, 'events': ev[-150:][::-1]}

@router.get('/api/srv/usage')
def srv_usage(day: str = None):
    import usage
    return {'today': usage.summary(day), 'history': usage.history(14),
            'note': 'Estimated from Chinnu\'s own calls x list prices. Exact bill: platform.openai.com/usage'}

SUGGESTIONS = [
    ('Cheaper brain for small talk', 'Route simple chit-chat to gpt-4o-mini or the local Ollama model; keep gpt-4.1 / realtime for tools.'),
    ('Exact OpenAI bill', 'Add an OpenAI Admin key so this page shows the real invoice numbers, not estimates.'),
    ('Energy use', 'Govee plugs report power; show watts and kWh per device.'),
    ('Backups status', 'Show the last GitHub backup and Nextcloud sync time here.'),
    ('Uptime history', 'Keep a 7-day timeline of PiDog online/offline and Wi-Fi drops.'),
]

@router.get('/api/srv/suggestions')
def srv_suggestions():
    return [{'title': t, 'text': x} for t, x in SUGGESTIONS]

@router.get('/server', response_class=HTMLResponse)
def server_page():
    return open(os.path.join(BASE, 'server.html'), encoding='utf-8').read()


@router.get('/api/net/devices')
def net_devices():
    import netscan; return netscan.listing()

@router.post('/api/net/scan')
def net_scan():
    import netscan; netscan.scan(); return netscan.listing()

@router.post('/api/net/label')
async def net_label(req: __import__('fastapi').Request):
    import netscan; d = await req.json(); return {'ok': netscan.set_label(d.get('mac', ''), d.get('label', ''))}


@router.get('/api/wifi/clients')
def wifi_clients():
    import wifishaper, os
    pw = ''
    try: pw = open(os.path.join(BASE, 'chinnu_wifi_pass')).read().strip()
    except Exception: pass
    return {'ssid': 'Chinnu-Hotspot', 'password': pw, 'devices': wifishaper.listing()}

@router.post('/api/wifi/limit')
async def wifi_limit(req: __import__('fastapi').Request):
    import wifishaper; d = await req.json()
    return {'ok': True, 'limit': wifishaper.set_limit(d['mac'], d.get('down'), d.get('up'), d.get('label'))}


@router.get('/api/wifi/qr.svg')
def wifi_qr():
    import io
    from segno import helpers as _sh_qr
    from fastapi.responses import Response
    pw = open(os.path.join(BASE, 'chinnu_wifi_pass')).read().strip()
    buf = io.BytesIO()
    _sh_qr.make_wifi(ssid='Chinnu-Hotspot', password=pw, security='WPA').save(buf, kind='svg', scale=6, border=2, dark='#000', light='#fff')
    return Response(buf.getvalue(), media_type='image/svg+xml', headers={'Cache-Control': 'no-store'})
