"""Network guard.
1) New-device alert: Telegram when a device never seen before joins router (netscan) or Chinnu-Hotspot (hotspot).
   Phones/Macs that only rotated their private MAC (same hostname as a known device) are ignored.
2) Self-heal: checks the router + internet every minute. If the server is cut off for 3 min it re-connects eth0 by itself;
   the outage is shown on Chinnu Hub (banner) and a Telegram message with the downtime is sent when it comes back.
Never powers anything off. State in netguard.json."""
import os, json, time, threading, subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(BASE, 'netguard.json')
GW, NET_IP = '192.168.1.1', '1.1.1.1'
_s = {'down_since': None, 'carrier': True, 'fixes': 0, 'last_fix': None}

def _load():
    try: return json.load(open(STATE))
    except Exception: return {'known': [], 'hosts': [], 'pending': []}

def _save(d): json.dump(d, open(STATE, 'w'), indent=1)

def tg(msg):
    try:
        import telegram_bot; telegram_bot.send(msg); return True
    except Exception as e:
        print('[netguard] tg', e, flush=True); return False

def hlog(kind, msg):
    try:
        import history; history.log(kind, msg)
    except Exception: pass

def _ping(ip):
    return subprocess.run(['ping', '-c', '1', '-W', '2', ip], capture_output=True).returncode == 0

def _carrier():
    try: return open('/sys/class/net/eth0/carrier').read().strip() == '1'
    except Exception: return False

def _hm(sec):
    m = int(sec // 60); return f'{m // 60}h {m % 60}m' if m >= 60 else f'{m} min'

# ---------------- 1. new devices ----------------
def _devices():
    out = []
    try:
        import netscan
        for mac, d in netscan._load()['devices'].items():
            out.append({'mac': mac, 'ip': d.get('ip'), 'host': (d.get('host') or '').replace('.lan', ''), 'vendor': d.get('vendor') or '',
                        'label': d.get('label') or '', 'net': 'router', 'online': d.get('online')})
    except Exception as e: print('[netguard] netscan', e, flush=True)
    try:
        import wifishaper
        for mac, ip in wifishaper.clients().items():
            out.append({'mac': mac, 'ip': ip, 'host': '', 'vendor': '', 'label': '', 'net': 'Chinnu-Hotspot', 'online': True})
    except Exception: pass
    return out

def check_new(first=False):
    st = _load(); known = set(st['known']); hosts = set(st['hosts'])
    new = []
    for d in _devices():
        h = d['host'].lower()
        if d['mac'] in known:
            if h: hosts.add(h)
            continue
        known.add(d['mac'])
        rotated = h and h in hosts          # same phone/Mac with a fresh private MAC
        if h: hosts.add(h)
        if first or rotated or not d['online']: continue
        new.append(d)
    st['known'], st['hosts'] = sorted(known), sorted(hosts); _save(st)
    for d in new:
        name = d['label'] or d['host'] or d['vendor'] or 'Unknown device'
        kind = 'phone/tablet (private MAC)' if 'random' in d['vendor'] else (d['vendor'] or 'unknown maker')
        msg = (f"🆕 Kotha device {d['net']} lo join ayyindi anna!\n"
               f"• Name: {name}\n• Type: {kind}\n• IP: {d['ip']}\n• MAC: {d['mac']}\n• Time: {time.strftime('%I:%M %p')}\n"
               f"Telisina device aithe Chinnu Hub → Home → Wi-Fi devices lo name pettu. Teliyakapothe router app lo block cheyyi.")
        hlog('alert', f"new device on {d['net']}: {name} {d['mac']}")
        if not tg(msg): st = _load(); st['pending'].append(msg); _save(st)

# ---------------- 2. self-heal ----------------
def _fix():
    _s['fixes'] += 1; _s['last_fix'] = time.time()
    for cmd in (['nmcli', 'dev', 'reapply', 'eth0'], ['nmcli', 'con', 'up', 'netplan-eth0']):
        r = subprocess.run(['sudo', '-n', *cmd], capture_output=True, text=True, timeout=60)
        print('[netguard] fix', ' '.join(cmd), r.returncode, (r.stderr or r.stdout).strip()[:120], flush=True)
        time.sleep(10)
        if _ping(GW): return True
    return False

def check_net():
    up = _ping(GW) or _ping(NET_IP)
    _s['carrier'] = _carrier()
    now = time.time()
    if not up:
        if not _s['down_since']:
            _s['down_since'] = now; hlog('alert', 'server internet DOWN' + ('' if _s['carrier'] else ' (Ethernet cable unplugged)'))
        elif _s['carrier'] and now - _s['down_since'] >= 180 and (not _s['last_fix'] or now - _s['last_fix'] >= 600):
            _fix()
        return
    if _s['down_since']:
        dur = now - _s['down_since']
        how = 'auto-fix tho malli connect chesanu' if _s['fixes'] else 'malli vachindi'
        msg = f"🔌 Server internet {_hm(dur)} down undi ({time.strftime('%I:%M %p', time.localtime(_s['down_since']))} nundi) — {how} anna."
        hlog('alert', f'server internet back after {_hm(dur)}')
        st = _load(); pend = st.get('pending', []); st['pending'] = []; _save(st)
        for m in pend + [msg]: tg(m)
        _s.update(down_since=None, fixes=0, last_fix=None)

def status():
    d = _s['down_since']
    return {'ok': d is None, 'down_since': time.strftime('%I:%M %p', time.localtime(d)) if d else None,
            'down_min': int((time.time() - d) // 60) if d else 0, 'cable': _s['carrier'], 'fixes': _s['fixes']}

def _loop():
    time.sleep(30)
    try: check_new(first=not os.path.exists(STATE))
    except Exception as e: print('[netguard]', e, flush=True)
    t_new = time.time()
    while True:
        try:
            check_net()
            if time.time() - t_new > 120 and not _s['down_since']:
                check_new(); t_new = time.time()
        except Exception as e:
            print('[netguard]', e, flush=True)
        time.sleep(60)

def start(): threading.Thread(target=_loop, daemon=True).start()
