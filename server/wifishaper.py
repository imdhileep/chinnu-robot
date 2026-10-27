"""Per-device speed limits for devices on "Chinnu-WiFi" (server hotspot on wlan0, 10.42.0.0/24).
Download = shaping on wlan0 egress, upload = wlan0 ingress redirected to ifb0. Limits stored by MAC
(wifilimits.json) so they follow the device when its IP changes. Re-applied every 20 s if clients change."""
import os, json, time, threading, subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'wifilimits.json')
IF, IFB = 'wlan0', 'ifb0'
_lock = threading.Lock()
_applied = [None]

def _sudo(*args):
    r = subprocess.run(['sudo', '-n', *args], capture_output=True, text=True, timeout=15)
    return r.returncode, (r.stderr or r.stdout).strip()

def _load():
    try: return json.load(open(DB))
    except Exception: return {}

def _save(d): json.dump(d, open(DB, 'w'), indent=1)

def clients():
    """MAC -> IP of devices currently associated with Chinnu-WiFi."""
    out = subprocess.run(['ip', 'neigh', 'show', 'dev', IF], capture_output=True, text=True).stdout
    res = {}
    for line in out.splitlines():
        p = line.split()
        if p and p[0].startswith('10.42.0.') and 'lladdr' in p and p[-1] not in ('FAILED', 'INCOMPLETE'):
            res[p[p.index('lladdr') + 1].lower()] = p[0]
    return res

_classmap = {}     # classid minor (int) -> mac, for live speed readings

def _rebuild(cl, lim):
    """Every connected device gets its own class (so we can measure it); limited ones get their rate."""
    _sudo('tc', 'qdisc', 'del', 'dev', IF, 'root'); _sudo('tc', 'qdisc', 'del', 'dev', IF, 'ingress')
    _sudo('modprobe', 'ifb'); _sudo('ip', 'link', 'add', IFB, 'type', 'ifb'); _sudo('ip', 'link', 'set', IFB, 'up')
    _sudo('tc', 'qdisc', 'del', 'dev', IFB, 'root')
    _classmap.clear()
    if not cl:
        _sudo('tc', 'qdisc', 'add', 'dev', IF, 'root', 'fq_codel'); return 0
    devs = sorted(cl.items())
    for dev, key, match in ((IF, 'down', 'dst'), (IFB, 'up', 'src')):
        _sudo('tc', 'qdisc', 'add', 'dev', dev, 'root', 'handle', '1:', 'htb', 'default', '999')
        _sudo('tc', 'class', 'add', 'dev', dev, 'parent', '1:', 'classid', '1:1', 'htb', 'rate', '1000mbit')
        _sudo('tc', 'class', 'add', 'dev', dev, 'parent', '1:1', 'classid', '1:999', 'htb', 'rate', '1000mbit')
        _sudo('tc', 'qdisc', 'add', 'dev', dev, 'parent', '1:999', 'fq_codel')
        for n, (mac, ip) in enumerate(devs, start=10):
            mbps = (lim.get(mac) or {}).get(key)
            rate = f'{float(mbps)}mbit' if mbps else '1000mbit'
            _classmap[n] = mac
            _sudo('tc', 'class', 'add', 'dev', dev, 'parent', '1:1', 'classid', f'1:{n}', 'htb', 'rate', rate, 'ceil', rate)
            _sudo('tc', 'qdisc', 'add', 'dev', dev, 'parent', f'1:{n}', 'fq_codel')
            _sudo('tc', 'filter', 'add', 'dev', dev, 'protocol', 'ip', 'parent', '1:', 'prio', '1', 'u32', 'match', 'ip', match, f'{ip}/32', 'flowid', f'1:{n}')
    _sudo('tc', 'qdisc', 'add', 'dev', IF, 'handle', 'ffff:', 'ingress')
    _sudo('tc', 'filter', 'add', 'dev', IF, 'parent', 'ffff:', 'protocol', 'ip', 'u32', 'match', 'u32', '0', '0', 'action', 'mirred', 'egress', 'redirect', 'dev', IFB)
    return sum(1 for m, _ in devs if (lim.get(m) or {}).get('down') or (lim.get(m) or {}).get('up'))

_prev = {}         # (dev, minor) -> (t, bytes)
def _class_bytes(dev):
    out = subprocess.run(["/usr/sbin/tc", "-s", "class", "show", "dev", dev], capture_output=True, text=True).stdout
    res, cur = {}, None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith('class htb 1:'):
            try: cur = int(line.split()[2].split(':')[1])
            except Exception: cur = None
        elif line.startswith('Sent ') and cur is not None:
            res[cur] = int(line.split()[1]); cur = None
    return res

def rates():
    """mac -> {'down': Mbps, 'up': Mbps, 'today_mb': MB since limits were (re)applied}"""
    now, out = time.time(), {}
    for dev, key in ((IF, 'down'), (IFB, 'up')):
        for minor, by in _class_bytes(dev).items():
            mac = _classmap.get(minor)
            if not mac: continue
            t0, b0 = _prev.get((dev, minor), (now, by))
            _prev[(dev, minor)] = (now, by)
            mbps = (by - b0) * 8 / 1e6 / (now - t0) if now - t0 > 0.5 and by >= b0 else 0.0
            e = out.setdefault(mac, {'down': 0.0, 'up': 0.0, 'mb': 0.0})
            e[key] = round(mbps, 2); e['mb'] = round(e['mb'] + by / 1e6, 1)
    return out

def apply(force=False):
    with _lock:
        cl, lim = clients(), _load()
        key = json.dumps([sorted(cl.items()), lim], sort_keys=True)
        if key == _applied[0] and not force: return
        n = _rebuild(cl, lim); _applied[0] = key
        print(f'[wifi] applied limits to {n} device(s), {len(cl)} connected', flush=True)

def set_limit(mac, down=None, up=None, label=None):
    d = _load(); e = d.setdefault(mac.lower(), {})
    if down is not None: e['down'] = max(0.0, float(down)) or None
    if up is not None: e['up'] = max(0.0, float(up)) or None
    if label is not None: e['label'] = label[:60]
    _save(d); apply(force=True); return e

def listing():
    cl, lim = clients(), _load()
    labels = {}
    try:
        import netscan
        labels = {m: (v.get('label') or v.get('host') or '') for m, v in netscan._load()['devices'].items()}
    except Exception: pass
    macs = sorted(set(cl) | set(lim))
    rt = {}
    try: rt = rates()
    except Exception: pass
    return [{'mac': m, 'ip': cl.get(m), 'online': m in cl, 'label': lim.get(m, {}).get('label') or labels.get(m, ''),
             'down': lim.get(m, {}).get('down'), 'up': lim.get(m, {}).get('up'),
             'now_down': rt.get(m, {}).get('down'), 'now_up': rt.get(m, {}).get('up'), 'mb': rt.get(m, {}).get('mb')} for m in macs]

def find(name):
    n = name.lower().strip()
    for r in listing():
        if n and (n in (r['label'] or '').lower() or n == r['mac'] or n == (r['ip'] or '')): return r
    return None

def _loop():
    time.sleep(10)
    while True:
        try: apply()
        except Exception as e: print('[wifi]', e, flush=True)
        time.sleep(20)

def start(): threading.Thread(target=_loop, daemon=True).start()
