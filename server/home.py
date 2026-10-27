"""Home devices for Chinnu: Cync bulbs over the Pi's Bluetooth mesh via cync2mqtt (local, no cloud).
Reads device list from ~/cync_mesh.yaml; publishes to acyncmqtt/set/<mesh_mac>/<id>."""
import os, json, yaml, subprocess, time

MESH_FILE = os.path.expanduser('~/cync_mesh.yaml')
TOPIC = 'acyncmqtt'
_devices = None  # name -> (mesh_mac, bulb_id)

def _load():
    global _devices
    if _devices is None:
        _devices = {}
        try:
            cfg = yaml.safe_load(open(MESH_FILE))
            for mesh_id, mesh in (cfg.get('meshconfig') or {}).items():
                for bid, bulb in (mesh.get('bulbs') or {}).items():
                    _devices[bulb.get('name', f'device_{bid}')] = (mesh['mac'], int(bid))
        except Exception as e:
            print('[home] mesh config missing:', e)
    return _devices

def ready():
    return bool(_load())

def devices():
    return [{'name': n, 'id': f'{m}/{b}', 'type': 'CyncLight'} for n, (m, b) in _load().items()]

def _find(name):
    devs = _load(); name = (name or '').lower().strip().replace(' ', '')
    for n in devs:
        if n.lower().replace(' ', '') == name: return n
    for n in devs:
        k = n.lower().replace(' ', '')
        if name in k or k in name: return n
    # "desk lamp 1" -> lamp1
    digits = ''.join(ch for ch in name if ch.isdigit())
    for n in devs:
        if digits and digits == ''.join(ch for ch in n if ch.isdigit()): return n
    return None

def _pub(mesh, bid, payload):
    r = subprocess.run(['mosquitto_pub', '-t', f'{TOPIC}/set/{mesh}/{bid}', '-m', json.dumps(payload)],
                       capture_output=True, text=True, timeout=5)
    return r.returncode == 0, r.stderr.strip()

# Groups: room = 3 bulbs in the ceiling fan, desk = stand lamp on the desk
GROUPS = {'room': ['Lamp1', 'Lamp2', 'Lamp3'], 'desk': ['Lamp4']}
ALIASES = {'room': ['room', 'roomlight', 'fan', 'fanlight', 'ceiling', 'ceilinglight', 'gadhi', 'roomlights'],
           'desk': ['desk', 'desklamp', 'desklight', 'standlamp', 'stand', 'table', 'tablelamp', 'lamp'],
           'all': ['all', 'alllights', 'anni', 'everything', 'lights']}

def _group(name):
    k = (name or '').lower().strip().replace(' ', '')
    for g, al in ALIASES.items():
        if k in al: return g
    return None

def light(name, action, value=None):
    g = _group(name)
    if g == 'all':
        return {'ok': True, 'group': 'all', 'results': all_lights(action, value)}
    if g:
        res = []
        for n in GROUPS[g]:
            res.append(_light_one(n, action, value)); time.sleep(0.25)
        return {'ok': all(r.get('ok') for r in res), 'group': g, 'devices': GROUPS[g], 'action': action, 'value': value, 'results': res}
    return _light_one(name, action, value)

def _light_one(name, action, value=None):
    n = _find(name)
    if n is None:
        return {'ok': False, 'error': f'no device named {name}', 'available': list(_load().keys())}
    mesh, bid = _load()[n]
    if action == 'on':
        payload = {'state': 'ON'}
    elif action == 'off':
        payload = {'state': 'OFF'}
    elif action == 'brightness':
        payload = {'state': 'ON', 'brightness': max(1, min(100, int(value or 50)))}
    else:
        return {'ok': False, 'error': f'unknown action {action}'}
    ok, err = _pub(mesh, bid, payload)
    return {'ok': ok, 'device': n, 'action': action, 'value': value, 'via': 'bluetooth-mesh', **({'error': err} if not ok else {})}

def all_lights(action, value=None):
    out = []
    for n in _load():
        out.append(_light_one(n, action, value)); time.sleep(0.25)
    return out

if __name__ == '__main__':
    import sys
    print('devices:', devices())
    if len(sys.argv) >= 3:
        print(light(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))


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
_devlog('light', lambda name, action, *a, **k: (f'light {name}' + (f' {a[0]}%' if action == 'brightness' and a and a[0] else ''), action != 'off'))
