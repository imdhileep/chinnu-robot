"""Chinnu app backend: every feature's live status, since-when, uptime % (24 h / 7 d), restart + mode toggles, alert feed.
Sampler thread runs only in the main dashboard (not CHINNU_LAN). Files: logs/uptime-YYYY-MM-DD.jsonl, uptime_state.json"""
import os, json, time, glob, threading, subprocess, requests
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
BASE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(BASE, 'logs')
STATE = os.path.join(BASE, 'uptime_state.json')
ROBOT, HDR = 'http://192.168.1.208:8090', {}
EVERY = 60

# (group, label, kind, target, restart)   restart: srvpage name | 'dashboard' | None
FEATURES = [
    ('core', 'Voice agent (Hey Chinnu)', 'unit', 'chinnu-voice', 'voice'),
    ('core', 'Wake word on PiDog', 'wake', None, 'pidog'),
    ('core', 'PiDog body', 'pidog', None, 'pidog'),
    ('core', 'Dashboard / this app', 'self', None, 'dashboard'),
    ('core', 'Home Wi-Fi app (Quest)', 'unit', 'chinnu-lan', 'lan'),
    ('core', 'Telegram bot', 'unit', 'chinnu-telegram', 'telegram'),
    ('core', 'Alexa bridge', 'unit', 'chinnu-alexa', 'alexa'),
    ('core', 'Lights bridge (Cync)', 'unit', 'cync2mqtt', 'cync'),
    ('core', 'Desk display', 'unit', 'chinnu-display-keepalive', 'display'),
    ('ai', 'OpenAI API', 'openai', None, None),
    ('ai', 'Ollama local brain', 'ollama', None, 'ollama'),
    ('home', 'Govee plugs', 'govee', None, None),
    ('home', 'Power strip', 'strip', None, None),
    ('home', 'Internet', 'net', None, None),
    ('home', 'Tailscale (outside access)', 'tailscale', None, None),
    ('home', 'Chinnu-WiFi hotspot', 'hotspot', None, None),
    ('media', 'External HDD', 'hdd', None, None),
    ('media', 'Nextcloud', 'docker', 'nextcloud-app-1', 'nextcloud'),
    ('media', 'Jellyfin', 'docker', 'jellyfin', 'jellyfin'),
    ('auto', 'Auto-charging', 'loop', 'autocharge', 'dashboard'),
    ('auto', 'Home auto (presence, quiet, door, briefing)', 'loop', 'home_auto', 'dashboard'),
    ('auto', 'Budget, battery log, auto-heal, reports', 'loop', 'ops', 'dashboard'),
    ('auto', 'Wi-Fi device scanner', 'loop', 'netscan', 'dashboard'),
    ('auto', 'Speed limiter', 'loop', 'wifishaper', 'dashboard'),
    ('auto', 'HDD watchdog', 'loop', 'hddwatch', 'dashboard'),
]
EXTRA_UNITS = {'cync': 'cync2mqtt', 'display': 'chinnu-display-keepalive'}
_slow = {}          # kind -> (t, ok, note)  for checks we don't want every minute
_cur = {}           # key -> {'ok','note','since'}
_lock = threading.Lock()

def key_of(f): return f[3] or f[2]

def _sh(cmd, t=8):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=t).stdout.strip()
    except Exception: return ''

def _slowcheck(kind, every, fn):
    t = _slow.get(kind)
    if t and time.time() - t[0] < every: return t[1], t[2]
    try: ok, note = fn()
    except Exception as e: ok, note = False, str(e)[:100]
    _slow[kind] = (time.time(), ok, note); return ok, note

def _openai():
    import voice
    voice.client.models.retrieve('gpt-4o-mini')
    try:
        import ops
        if ops.saver_on(): return True, 'reachable · saver mode ON'
    except Exception: pass
    return True, 'reachable'

def _home(part):
    import mobile
    d = mobile.home_state(fresh=1)
    if part == 'govee':
        g = d.get('govee')
        if not g: return False, d.get('govee_error', 'no answer')
        off = [k for k, v in g.items() if not v.get('online')]
        return not off, ('all online' if not off else 'offline: ' + ', '.join(off))
    s = d.get('strip')
    return (bool(s), 'connected' if s else d.get('strip_error', 'no answer'))

def check_all():
    """Returns {key: (ok, note)} for every feature."""
    out = {}
    units = [f[3] for f in FEATURES if f[2] == 'unit']
    states = _sh(['systemctl', 'is-active'] + units).splitlines()
    ustate = dict(zip(units, states + [''] * len(units)))
    dps = _sh(['docker', 'ps', '-a', '--format', '{{.Names}}|{{.Status}}'])
    dstate = {l.split('|', 1)[0]: l.split('|', 1)[1] for l in dps.splitlines() if '|' in l}
    loops = set()
    for t in threading.enumerate():
        tg = getattr(t, '_target', None)
        if tg is not None and t.is_alive(): loops.add(getattr(tg, '__module__', ''))
    health = None
    try: health = requests.get(f'{ROBOT}/health', headers=HDR, timeout=3).json()
    except Exception: pass
    for f in FEATURES:
        g, label, kind, tgt, rs = f; k = key_of(f)
        try:
            if kind == 'unit':
                s = ustate.get(tgt, ''); out[k] = (s == 'active', s or 'unknown')
            elif kind == 'self': out[k] = (True, 'running')
            elif kind == 'pidog': out[k] = (health is not None, 'online' if health else 'not answering')
            elif kind == 'wake':
                kws = (health or {}).get('kws')
                out[k] = (bool(health) and bool(kws), f'listening ({kws})' if kws else 'off' if health else 'PiDog offline')
            elif kind == 'docker':
                s = dstate.get(tgt, 'not found'); out[k] = (s.startswith('Up'), s)
            elif kind == 'loop': out[k] = (tgt in loops, 'running' if tgt in loops else 'stopped - restart dashboard')
            elif kind == 'openai': out[k] = _slowcheck('openai', 300, _openai)
            elif kind == 'ollama':
                r = requests.get('http://127.0.0.1:11434/api/tags', timeout=4).json()
                out[k] = (True, ', '.join(m['name'] for m in r.get('models', [])) or 'no models')
            elif kind == 'govee': out[k] = _slowcheck('govee', 600, lambda: _home('govee'))
            elif kind == 'strip': out[k] = _slowcheck('strip', 600, lambda: _home('strip'))
            elif kind == 'net':
                ok = subprocess.run(['ping', '-c', '1', '-W', '2', '1.1.1.1'], capture_output=True).returncode == 0
                out[k] = (ok, 'online' if ok else 'no internet')
            elif kind == 'tailscale':
                j = json.loads(_sh(['tailscale', 'status', '--json']) or '{}'); st = j.get('BackendState', '?')
                out[k] = (st == 'Running', st)
            elif kind == 'hotspot':
                a = _sh(['nmcli', '-t', '-f', 'NAME,DEVICE', 'con', 'show', '--active'])
                ok = any(l.endswith(':wlan0') for l in a.splitlines()); out[k] = (ok, 'Chinnu-WiFi up' if ok else 'down')
            elif kind == 'hdd':
                ok = subprocess.run(['findmnt', '/mnt/hdd'], capture_output=True).returncode == 0
                out[k] = (ok, _sh(['sh', '-c', "df -h /mnt/hdd | awk 'NR==2{print $5\" used of \"$2}'"]) if ok else 'NOT MOUNTED')
        except Exception as e:
            out[k] = (False, str(e)[:100])
    return out

def _load_state():
    try: return json.load(open(STATE))
    except Exception: return {}

def sample():
    res = check_all(); now = time.time()
    names = {key_of(f): f[1] for f in FEATURES}
    with _lock:
        if not _cur: _cur.update(_load_state())
        for k, (ok, note) in res.items():
            old = _cur.get(k)
            if not old or old.get('ok') != ok:
                if old is not None and k not in ('openai',):
                    try:
                        import history
                        history.log('alert', f"{names.get(k, k)} {'back UP' if ok else 'DOWN'} ({note})")
                    except Exception: pass
                _cur[k] = {'ok': ok, 'note': note, 'since': now}
            else:
                _cur[k].update(note=note)
        json.dump(_cur, open(STATE, 'w'))
    os.makedirs(LOGS, exist_ok=True)
    with open(os.path.join(LOGS, time.strftime('uptime-%Y-%m-%d.jsonl')), 'a') as fh:
        fh.write(json.dumps({'t': int(now), 's': {k: int(v[0]) for k, v in res.items()}}) + '\n')

_pct_cache = {'t': 0, 'v': {}}
def percents():
    if time.time() - _pct_cache['t'] < 120: return _pct_cache['v']
    now = time.time(); c24, c7, n24, n7 = {}, {}, {}, {}
    for p in sorted(glob.glob(os.path.join(LOGS, 'uptime-*.jsonl')))[-8:]:
        for line in open(p):
            try: d = json.loads(line)
            except Exception: continue
            age = now - d['t']
            if age > 7 * 86400: continue
            for k, v in d['s'].items():
                n7[k] = n7.get(k, 0) + 1; c7[k] = c7.get(k, 0) + v
                if age <= 86400: n24[k] = n24.get(k, 0) + 1; c24[k] = c24.get(k, 0) + v
    v = {k: {'d1': round(100 * c24.get(k, 0) / n24[k], 1) if n24.get(k) else None,
             'd7': round(100 * c7[k] / n7[k], 1), 'hours': round(n7[k] * EVERY / 3600, 1)} for k in n7}
    _pct_cache.update(t=now, v=v); return v

def timeline(key, hours=24, buckets=48):
    """Uptime strip for one feature: list of 1/0/None per bucket (oldest first)."""
    now = time.time(); size = hours * 3600 / buckets; b = [[0, 0] for _ in range(buckets)]
    for p in sorted(glob.glob(os.path.join(LOGS, 'uptime-*.jsonl')))[-2:]:
        for line in open(p):
            try: d = json.loads(line)
            except Exception: continue
            i = int((d['t'] - (now - hours * 3600)) // size)
            if 0 <= i < buckets and key in d['s']: b[i][0] += d['s'][key]; b[i][1] += 1
    return [None if n == 0 else round(u / n, 2) for u, n in b]

def _loop():
    time.sleep(20)
    while True:
        try: sample()
        except Exception as e: print('[uptime]', e, flush=True)
        time.sleep(EVERY)

def start(robot, hdr):
    global ROBOT, HDR
    ROBOT, HDR = robot, hdr
    threading.Thread(target=_loop, daemon=True).start()

_tl_cache = {'t': 0, 'v': {}}
def timelines(hours=24, buckets=48):
    if time.time() - _tl_cache['t'] < 120: return _tl_cache['v']
    now = time.time(); size = hours * 3600 / buckets; acc = {}
    for p in sorted(glob.glob(os.path.join(LOGS, 'uptime-*.jsonl')))[-2:]:
        for line in open(p):
            try: d = json.loads(line)
            except Exception: continue
            i = int((d['t'] - (now - hours * 3600)) // size)
            if not 0 <= i < buckets: continue
            for k, v in d['s'].items():
                b = acc.setdefault(k, [[0, 0] for _ in range(buckets)]); b[i][0] += v; b[i][1] += 1
    v = {k: [None if n == 0 else round(u / n, 2) for u, n in b] for k, b in acc.items()}
    _tl_cache.update(t=now, v=v); return v

def _modes():
    m = {}
    try:
        import behaviors; s = behaviors.status(); m['guard'] = s.get('guard'); m['follow'] = s.get('follow')
        m['guard_note'] = s.get('guard_note'); m['alerts'] = s.get('alerts')
    except Exception: pass
    try: import ops; m['saver'] = ops.saver_on()
    except Exception: pass
    try:
        import home_auto; h = home_auto.status(); m['presence'] = h.get('presence'); m['quiet'] = h.get('quiet_now')
    except Exception: pass
    try:
        import owner; o = owner.status(); m['owner'] = o.get('owner'); m['owner_left'] = o.get('seconds_left')
    except Exception: pass
    try:
        import autocharge; a = autocharge.status(); m['charging'] = a.get('charger_on'); m['battery'] = a.get('percent')
    except Exception: pass
    return m

@router.get('/api/app/features')
def app_features():
    with _lock:
        cur = dict(_cur) or _load_state()
    pc, tl = percents(), timelines()
    out = []
    for f in FEATURES:
        g, label, kind, tgt, rs = f; k = key_of(f); c = cur.get(k, {})
        out.append({'key': k, 'group': g, 'label': label, 'ok': c.get('ok'), 'note': c.get('note', 'checking...'),
                    'since': c.get('since'), 'd1': pc.get(k, {}).get('d1'), 'd7': pc.get(k, {}).get('d7'),
                    'tl': tl.get(k, []), 'restart': rs})
    up = sum(1 for x in out if x['ok']); return {'features': out, 'up': up, 'total': len(out), 'modes': _modes(),
            'server_up': _sh(['uptime', '-p']), 'now': time.time()}

@router.post('/api/app/check')
def app_check():
    _slow.clear(); sample(); _pct_cache['t'] = 0; _tl_cache['t'] = 0; return app_features()

@router.post('/api/app/restart/{key}')
def app_restart(key: str):
    f = next((f for f in FEATURES if key_of(f) == key), None)
    if not f or not f[4]: return JSONResponse({'ok': False, 'note': 'no restart for this'}, status_code=400)
    rs = f[4]
    if rs in EXTRA_UNITS:
        r = subprocess.run(['sudo', '-n', 'systemctl', 'restart', EXTRA_UNITS[rs]], capture_output=True, text=True, timeout=60)
        res = {'ok': r.returncode == 0, 'note': r.stderr.strip()[:200] or f'{EXTRA_UNITS[rs]} restarted'}
    else:
        import srvpage; res = srvpage.srv_restart(rs)
        if not isinstance(res, dict): res = {'ok': False, 'note': 'failed'}
    def later():
        time.sleep(15); _slow.clear()
        try: sample()
        except Exception: pass
    threading.Thread(target=later, daemon=True).start()
    return res

SKIP = {'chintu', 'chinnu', 'device', 'light', 'action', 'strip', 'govee', 'photo'}
@router.get('/api/app/alerts')
def app_alerts(days: int = 3):
    items = []
    for p in sorted(glob.glob(os.path.join(LOGS, 'chinnu-*.jsonl')))[-days:]:
        day = os.path.basename(p)[7:17]
        for line in open(p, encoding='utf-8'):
            try: d = json.loads(line)
            except Exception: continue
            if d.get('kind') in SKIP: continue
            items.append({'day': day, 't': d.get('t', ''), 'kind': d.get('kind', ''), 'text': d.get('text', '')})
    return {'items': items[::-1][:200]}
