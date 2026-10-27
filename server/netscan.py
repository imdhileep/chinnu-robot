"""Home network inventory: every 5 min ping-sweep the LAN (nmap -sn), read MACs from the ARP table,
keep first/last seen + online minutes per day. Stored in netdevices.json. Labels editable from the Server page."""
import os, re, json, time, threading, subprocess, socket

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'netdevices.json')
SUBNET = '192.168.1.0/24'
EVERY = 300
_lock = threading.Lock()
_vendors = None
KNOWN = {'192.168.1.208': 'Chinnu PiDog', '192.168.1.226': 'Chinnu server (wired)', '192.168.1.227': 'Chinnu server (Wi-Fi)',
         '192.168.1.1': 'router router', '22:e9:0b:91:c7:83': 'Meta Quest 3'}

def _load():
    try: return json.load(open(DB))
    except Exception: return {'devices': {}, 'last_scan': None}

def _save(d):
    with _lock:
        json.dump(d, open(DB + '.tmp', 'w'), indent=1); os.replace(DB + '.tmp', DB)

def _vendor(mac):
    global _vendors
    if _vendors is None:
        _vendors = {}
        try:
            for line in open('/usr/share/nmap/nmap-mac-prefixes', encoding='utf-8', errors='ignore'):
                if line[:1] != '#' and len(line) > 7: _vendors[line[:6].upper()] = line[7:].strip()
        except Exception: pass
    p = mac.replace(':', '').upper()[:6]
    if int(p[1], 16) & 2: return 'private (random) MAC - phone/tablet/watch'
    return _vendors.get(p, '')

def scan():
    out = subprocess.run(['nmap', '-sn', '-T4', SUBNET], capture_output=True, text=True, timeout=180).stdout
    names = {}
    for m in re.finditer(r'Nmap scan report for (?:(\S+) \()?(\d+\.\d+\.\d+\.\d+)\)?', out):
        names[m.group(2)] = m.group(1) or ''
    neigh = subprocess.run(['ip', 'neigh'], capture_output=True, text=True).stdout
    seen = {}
    for line in neigh.splitlines():
        p = line.split()
        if 'lladdr' in p and p[-1] not in ('FAILED', 'INCOMPLETE'):
            ip, mac = p[0], p[p.index('lladdr') + 1].lower()
            if not ip.startswith('192.168.1.'): continue
            if ip in names or p[-1] in ('REACHABLE', 'DELAY', 'STALE'): seen[mac] = ip
    # this server itself (not in its own ARP table)
    for iface in ('eth0', 'wlan0'):
        try:
            mac = open(f'/sys/class/net/{iface}/address').read().strip()
            ip = subprocess.run(['ip', '-4', '-o', 'addr', 'show', iface], capture_output=True, text=True).stdout.split()[3].split('/')[0]
            seen[mac] = ip
        except Exception: pass
    now = time.time(); day = time.strftime('%Y-%m-%d')
    d = _load(); devs = d['devices']
    for mac, dv in devs.items(): dv['online'] = False
    for mac, ip in seen.items():
        dv = devs.setdefault(mac, {'first_seen': time.strftime('%Y-%m-%d %H:%M'), 'label': '', 'minutes': {}})
        dv.update(ip=ip, online=True, last_seen=time.strftime('%Y-%m-%d %H:%M'), host=names.get(ip, '') or dv.get('host', ''),
                  vendor=dv.get('vendor') or _vendor(mac))
        if not dv.get('label'): dv['label'] = KNOWN.get(mac) or KNOWN.get(ip, '')
        dv['minutes'][day] = dv['minutes'].get(day, 0) + EVERY // 60
        dv['minutes'] = dict(sorted(dv['minutes'].items())[-14:])
    d['last_scan'] = time.strftime('%Y-%m-%d %H:%M:%S'); d['count_online'] = len(seen)
    _save(d)
    return d

def set_label(mac, label):
    d = _load()
    if mac in d['devices']: d['devices'][mac]['label'] = label[:60]; _save(d); return True
    return False

def listing():
    d = _load(); day = time.strftime('%Y-%m-%d')
    rows = [{'mac': m, **{k: v for k, v in dv.items() if k != 'minutes'}, 'today_min': dv.get('minutes', {}).get(day, 0)}
            for m, dv in d['devices'].items()]
    rows.sort(key=lambda r: (not r.get('online'), (r.get('label') or r.get('host') or 'zzz').lower()))
    return {'last_scan': d.get('last_scan'), 'online': sum(1 for r in rows if r.get('online')), 'total': len(rows), 'devices': rows}

def _loop():
    time.sleep(20)
    while True:
        try: scan()
        except Exception as e: print('[netscan]', e, flush=True)
        time.sleep(EVERY)

def start():
    threading.Thread(target=_loop, daemon=True).start()
