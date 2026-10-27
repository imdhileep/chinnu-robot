"""Local control of the Tuya/GHome PM03 power strip (tinytuya, LAN, no cloud).
Outlet names come from config.yaml `strip:` (e.g. {1: fan, 2: lamp, 3: heater, usb: charger})."""
import json, os, threading, yaml
import tinytuya

HERE = os.path.dirname(os.path.abspath(__file__))
_lock = threading.Lock()
_dev = None
DPS = {'1': 1, '2': 2, '3': 3, 'usb': 7}
CFG = (yaml.safe_load(open(os.path.join(HERE, 'config.yaml'), encoding='utf-8-sig')) or {}).get('strip', {}) or {}
NAMES = {str(k): str(v) for k, v in (CFG.get('outlets') or {}).items()}   # outlet -> friendly name

def _device():
    global _dev
    if _dev is None:
        d = json.load(open(os.path.join(HERE, 'tuya_devices.json')))[0]
        _dev = tinytuya.OutletDevice(d['id'], d['ip'], d['key'], version=float(d.get('version') or 3.4))
        _dev.set_socketTimeout(4); _dev.set_socketRetryLimit(2)
    return _dev

def _resolve(outlet):
    o = str(outlet).strip().lower().replace('switch', '').replace('outlet', '').strip()
    if o in DPS: return o
    for k, n in NAMES.items():
        if o == n.lower(): return k
    if o == 'all': return 'all'
    raise ValueError(f'unknown outlet {outlet!r}; use 1,2,3,usb,all or names {list(NAMES.values())}')

def status():
    with _lock:
        st = _device().status().get('dps', {})
    return {k: {'name': NAMES.get(k, f'switch {k}'), 'on': bool(st.get(str(v), False))} for k, v in DPS.items()}

def set_outlet(outlet, on):
    key = _resolve(outlet)
    with _lock:
        dev = _device()
        if key == 'all':
            for v in DPS.values(): dev.set_status(bool(on), switch=v)
        else:
            dev.set_status(bool(on), switch=DPS[key])
    return status()


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
_devlog('set_outlet', lambda outlet, on, *a, **k: ('strip ' + str(outlet), on))
