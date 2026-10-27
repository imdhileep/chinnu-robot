"""Govee smart plugs (H5082 dual plugs) via the Govee cloud API.
config.yaml `govee:` -> sockets: {"<deviceName>": {1: name, 2: name}}, locked: [names never switched OFF],
groups: {group name: [socket names]}."""
import os, time, uuid, requests, yaml
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, '.env'))
KEY = os.environ.get('GOVEE_API_KEY', '')
BASE = 'https://openapi.api.govee.com/router/api/v1'
HDR = {'Govee-API-Key': KEY, 'Content-Type': 'application/json'}
CFG = (yaml.safe_load(open(os.path.join(HERE, 'config.yaml'), encoding='utf-8-sig')) or {}).get('govee', {}) or {}
SOCKETS = {str(k).lower(): {str(i): str(n).lower() for i, n in (v or {}).items()} for k, v in (CFG.get('sockets') or {}).items()}
LOCKED = {str(x).lower() for x in (CFG.get('locked') or [])}
GROUPS = {str(k).lower(): [str(x).lower() for x in v] for k, v in (CFG.get('groups') or {}).items()}
_cache = {'t': 0, 'devs': []}

def devices(force=False):
    if force or time.time() - _cache['t'] > 600:
        r = requests.get(f'{BASE}/user/devices', headers=HDR, timeout=15); r.raise_for_status()
        _cache['devs'] = [d for d in r.json().get('data', []) if d.get('type') == 'devices.types.socket']
        _cache['t'] = time.time()
    return _cache['devs']

def _dev(name):
    for d in devices():
        if d['deviceName'].lower() == name.lower(): return d
    raise ValueError(f'unknown plug {name!r}')

def _sockets_for(target):
    """Resolve a target to a list of (device_name, socket_idx, friendly_name)."""
    t = str(target).strip().lower()
    if t in GROUPS:
        out = []
        for n in GROUPS[t]: out += _sockets_for(n)
        return out
    for dn, socks in SOCKETS.items():
        for idx, name in socks.items():
            if name == t: return [(dn, idx, name)]
    for d in devices():
        dn = d['deviceName'].lower(); names = SOCKETS.get(dn, {})
        if t == dn: return [(dn, i, names.get(i, f'{dn} {i}')) for i in ('1', '2')]
        if t.startswith(dn) and t[len(dn):].strip() in ('1', '2'):
            i = t[len(dn):].strip(); return [(dn, i, names.get(i, f'{dn} {i}'))]
    raise ValueError(f'unknown plug {target!r}; names: {[n for s in SOCKETS.values() for n in s.values()]}, groups: {list(GROUPS)}')

def _control(d, instance, value):
    body = {'requestId': str(uuid.uuid4()), 'payload': {'sku': d['sku'], 'device': d['device'],
            'capability': {'type': 'devices.capabilities.on_off' if instance == 'powerSwitch' else 'devices.capabilities.toggle',
                           'instance': instance, 'value': value}}}
    r = requests.post(f'{BASE}/device/control', headers=HDR, json=body, timeout=15)
    return r.status_code == 200 and r.json().get('code') == 200

def state(d):
    body = {'requestId': str(uuid.uuid4()), 'payload': {'sku': d['sku'], 'device': d['device']}}
    r = requests.post(f'{BASE}/device/state', headers=HDR, json=body, timeout=15)
    caps = (r.json().get('payload') or {}).get('capabilities', []) if r.ok else []
    return {c['instance']: c.get('state', {}).get('value') for c in caps}

def list_plugs():
    return [{'device': d['deviceName'], 'socket1': SOCKETS.get(d['deviceName'].lower(), {}).get('1'),
             'socket2': SOCKETS.get(d['deviceName'].lower(), {}).get('2')} for d in devices()] + [{'groups': GROUPS, 'locked': sorted(LOCKED)}]

def set_plug(target, on):
    results, refused = [], []
    for dn, idx, name in _sockets_for(target):
        if not on and name in LOCKED:
            refused.append(name); continue
        d = _dev(dn)
        if on:   # a socket toggle only powers if the plug master switch is on
            st = state(d)
            if not st.get('powerSwitch'): _control(d, 'powerSwitch', 1)
        ok = _control(d, f'socketToggle{idx}', 1 if on else 0)
        results.append({'socket': name, 'on': bool(on), 'ok': ok})
    out = {'ok': all(r['ok'] for r in results) if results else not refused, 'done': results}
    if refused:
        out['refused'] = refused
        out['note'] = 'These are protected (server / internet) and are never switched off by Chinnu.'
    return out

def status(target=None):
    devs = [_dev(s[0]) for s in _sockets_for(target)] if target else devices()
    out = {}
    for d in {x['deviceName']: x for x in devs}.values():
        st = state(d); names = SOCKETS.get(d['deviceName'].lower(), {})
        out[d['deviceName']] = {'online': st.get('online'), names.get('1', 'socket 1'): bool(st.get('socketToggle1')),
                                names.get('2', 'socket 2'): bool(st.get('socketToggle2'))}
    return out


# ---- device usage log (server page: lights & accessories timeline) ----
def _devlog(fn_name, label_fn):
    import functools, sys, os
    orig = globals()[fn_name]
    @functools.wraps(orig)
    def w(*a, **kw):
        r = orig(*a, **kw)
        try:
            import history
            name, on = label_fn(*a, **kw)
            src = os.environ.get('CHINNU_SRC') or os.path.basename(sys.argv[0] or '?')
            history.log('device', f"{name} {'ON' if on else 'OFF'}", device=str(name), on=bool(on), src=src,
                        ok=bool(r.get('ok', True)) if isinstance(r, dict) else True)
        except Exception as e: print('[devlog]', e, flush=True)
        return r
    globals()[fn_name] = w
_devlog('set_plug', lambda target, on, *a, **k: (target, on))
