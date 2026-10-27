"""Auto-charging for Chinnu (PiDog): switches the Govee 'pidog charger' socket by battery voltage.
ON  when voltage < low_v, or when the robot has been unreachable for a while (battery probably flat).
OFF when voltage >= full_v on two readings in a row, or after max_hours of charging (safety).
Runs as a background thread inside the dashboard. State in autocharge.json."""
import json, time, pathlib, threading, requests, yaml

DIR = pathlib.Path(__file__).parent
STATE = DIR / 'autocharge.json'
SOCKET = 'pidog charger'

def _cfg():
    c = (yaml.safe_load(open(DIR / 'config.yaml', encoding='utf-8-sig')) or {}).get('autocharge') or {}
    return {'enabled': c.get('enabled', True), 'low_v': float(c.get('low_v', 7.3)), 'full_v': float(c.get('full_v', 8.3)),
            'max_hours': float(c.get('max_hours', 5)), 'offline_min': float(c.get('offline_min', 6)), 'every_s': int(c.get('every_s', 120))}

def _load():
    try: return json.loads(STATE.read_text())
    except Exception: return {}

def _save(s): STATE.write_text(json.dumps(s, indent=1))

def _log(msg):
    print('[autocharge]', msg, flush=True)
    try:
        import history; history.log('charge', msg)
    except Exception: pass

def _battery(robot, hdr):
    try:
        b = requests.get(f'{robot}/battery', headers=hdr, timeout=6).json()
        return b.get('voltage'), b.get('percent')
    except Exception:
        return None, None

def _set(on):
    import govee_plug
    r = govee_plug.set_plug(SOCKET, on)
    return bool(r.get('ok'))

def _is_on():
    import govee_plug
    try: return bool(govee_plug.status(SOCKET).get('Misev', {}).get(SOCKET))
    except Exception: return None

def status():
    s = _load(); c = _cfg()
    return {**c, **s}

def step(robot, hdr):
    c = _cfg(); s = _load(); now = time.time()
    if not c['enabled']: return
    v, pct = _battery(robot, hdr)
    on = _is_on()
    if on is None: return
    s.update(voltage=v, percent=pct, charger_on=on, checked=time.strftime('%Y-%m-%d %H:%M:%S'))
    if on and not s.get('on_since'): s['on_since'] = now
    if not on: s['on_since'] = None; s['full_hits'] = 0
    if on and s.get('on_since') and (now - s['on_since']) / 3600 > c['max_hours']:
        if _set(False):
            _log(f"safety stop after {(now - s['on_since']) / 3600:.1f} h - charger OFF" + (" (robot offline)" if v is None else ""))
            s['on_since'] = None; s['full_hits'] = 0; s['charger_on'] = False
        _save(s); return
    if v is None:
        s['offline_since'] = s.get('offline_since') or now
        if not on and now - s['offline_since'] > c['offline_min'] * 60:
            if _set(True): s['on_since'] = now; _log(f'robot offline {int((now - s["offline_since"]) / 60)} min - charger ON (battery may be flat)')
    else:
        s['offline_since'] = None
        if not on and v < c['low_v']:
            if _set(True): s['on_since'] = now; s['full_hits'] = 0; _log(f'battery low {v} V ({pct}%) - charger ON')
        elif on:
            s['full_hits'] = s.get('full_hits', 0) + 1 if v >= c['full_v'] else 0
            hours = (now - (s.get('on_since') or now)) / 3600
            if s['full_hits'] >= 2 or hours > c['max_hours']:
                why = f'full {v} V ({pct}%)' if s['full_hits'] >= 2 else f'safety stop after {hours:.1f} h'
                if _set(False): s['on_since'] = None; s['full_hits'] = 0; s['charger_on'] = False; _log(f'{why} - charger OFF')
    _save(s)

def run(robot, hdr):
    time.sleep(30)
    while True:
        try: step(robot, hdr)
        except Exception as e: print('[autocharge] error', e, flush=True)
        time.sleep(_cfg()['every_s'])

def start(robot, hdr):
    threading.Thread(target=run, args=(robot, hdr), daemon=True).start()
