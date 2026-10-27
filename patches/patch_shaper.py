p = 'wifishaper.py'; s = open(p).read()
a = s.index('def _rebuild(cl, lim):'); b = s.index('def apply(force=False):')
new_rebuild = '''_classmap = {}     # classid minor (int) -> mac, for live speed readings

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
    out = subprocess.run(['tc', '-s', 'class', 'show', 'dev', dev], capture_output=True, text=True).stdout
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

'''
s = s[:a] + new_rebuild + s[b:]
old = """    return [{'mac': m, 'ip': cl.get(m), 'online': m in cl, 'label': lim.get(m, {}).get('label') or labels.get(m, ''),
             'down': lim.get(m, {}).get('down'), 'up': lim.get(m, {}).get('up')} for m in macs]"""
new = """    rt = {}
    try: rt = rates()
    except Exception: pass
    return [{'mac': m, 'ip': cl.get(m), 'online': m in cl, 'label': lim.get(m, {}).get('label') or labels.get(m, ''),
             'down': lim.get(m, {}).get('down'), 'up': lim.get(m, {}).get('up'),
             'now_down': rt.get(m, {}).get('down'), 'now_up': rt.get(m, {}).get('up'), 'mb': rt.get(m, {}).get('mb')} for m in macs]"""
assert s.count(old) == 1; s = s.replace(old, new)
open(p, 'w').write(s)

# ---- srvpage: QR code for joining Chinnu-WiFi ----
p = 'srvpage.py'; s = open(p).read()
if '/api/wifi/qr.svg' not in s:
    s += '''

@router.get('/api/wifi/qr.svg')
def wifi_qr():
    import segno, io
    from fastapi.responses import Response
    pw = open(os.path.join(BASE, 'chinnu_wifi_pass')).read().strip()
    buf = io.BytesIO()
    segno.helpers.make_wifi(ssid='Chinnu-WiFi', password=pw, security='WPA').save(buf, kind='svg', scale=6, border=2, dark='#000', light='#fff')
    return Response(buf.getvalue(), media_type='image/svg+xml', headers={'Cache-Control': 'no-store'})
'''
open(p, 'w').write(s)
print('ok')
