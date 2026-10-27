"""Extra sections for Chinnu's nightly Telegram report (ops.report_text):
who was home, Wi-Fi usage per device, new devices, outages and alerts.
Also samples per-device data use on the server hotspot every 5 min (logs/wifiusage-YYYY-MM-DD.json)."""
import os, json, time, glob, threading, collections

BASE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(BASE, 'logs')

def _day(day=None): return day or time.strftime('%Y-%m-%d')

def _hm(mins):
    mins = int(mins); return f'{mins // 60}h {mins % 60}m' if mins >= 60 else f'{mins}m'

def _events(day, kinds=None):
    p = os.path.join(LOGS, f'chinnu-{day}.jsonl'); out = []
    if not os.path.exists(p): return out
    for line in open(p, encoding='utf-8'):
        try: d = json.loads(line)
        except Exception: continue
        if not kinds or d.get('kind') in kinds: out.append(d)
    return out

# ---------------- hotspot data sampler ----------------
def _wf(day=None): return os.path.join(LOGS, f'wifiusage-{_day(day)}.json')

def wifi_sample():
    import wifishaper
    raw = {}
    for dev in (wifishaper.IF, wifishaper.IFB):
        for minor, by in wifishaper._class_bytes(dev).items():
            mac = wifishaper._classmap.get(minor)
            if mac: raw[(mac, dev)] = by
    p = _wf()
    try: d = json.load(open(p))
    except Exception:
        d = {'last': {}, 'mb': {}}
        prev = [x for x in sorted(glob.glob(os.path.join(LOGS, 'wifiusage-*.json'))) if x != p]
        if prev:
            try: d['last'] = json.load(open(prev[-1])).get('last', {})
            except Exception: pass
    for (mac, dev), by in raw.items():
        k = f'{mac}|{dev}'; last = d['last'].get(k)
        delta = 0 if last is None else (by - last if by >= last else by)
        d['mb'][mac] = round(d['mb'].get(mac, 0) + delta / 1e6, 2)
        d['last'][k] = by
    json.dump(d, open(p, 'w'))

def _loop():
    time.sleep(60)
    while True:
        try: wifi_sample()
        except Exception as e: print('[nightly]', e, flush=True)
        time.sleep(300)

def start(): threading.Thread(target=_loop, daemon=True).start()

# ---------------- sections ----------------
def presence_lines(day=None):
    day = _day(day); ev = _events(day, ('presence',))
    # state at midnight = last presence event of earlier days (default home)
    home = True
    for p in sorted(glob.glob(os.path.join(LOGS, 'chinnu-*.jsonl')), reverse=True):
        d0 = os.path.basename(p)[7:17]
        if d0 >= day: continue
        prev = _events(d0, ('presence',))
        if prev: home = 'came home' in prev[-1].get('text', ''); break
    end = time.strftime('%H:%M') if day == time.strftime('%Y-%m-%d') else '23:59'
    t_prev, mins, moves = '00:00', 0, []
    def m(t): h, mi = t[:5].split(':'); return int(h) * 60 + int(mi)
    for e in ev:
        t = e['t'][:5]; arrived = 'came home' in e.get('text', '')
        if home: mins += m(t) - m(t_prev)
        moves.append(('🏠 back ' if arrived else '🚶 left ') + t)
        home, t_prev = arrived, t
    if home: mins += m(end) - m(t_prev)
    lines = [f"🏠 Chintu home: {_hm(mins)}" + (f" ({', '.join(moves)})" if moves else ' (all day)')]
    try:
        import netscan
        ds = netscan.listing()['devices']; own = set(m.lower() for m in _owner_macs())
        def phoney(d):
            h = (d.get('host') or d.get('label') or '').lower()
            return any(w in h for w in ('iphone', 'phone', 'galaxy', 's2', 'a2', 'pixel', 'tab', 'ipad')) and 'mac' not in h
        ppl, seen = [], set()
        for d in sorted(ds, key=lambda d: -d.get('today_min', 0)):
            n = _name(d)
            if d['mac'] in own or d.get('today_min', 0) < 15 or not phoney(d) or n in seen: continue
            seen.add(n); ppl.append(d)
        if ppl:
            ppl.sort(key=lambda d: -d['today_min'])
            lines.append('👨‍👩‍👦 Other phones/tablets home: ' + ', '.join(
                f"{_name(d)} {_hm(d['today_min'])}" for d in ppl[:6]))
    except Exception: pass
    return lines

def _owner_macs():
    try:
        import yaml
        return (yaml.safe_load(open(os.path.join(BASE, 'config.yaml'), encoding='utf-8-sig')) or {}).get('home_auto', {}).get('owner_macs', [])
    except Exception: return []

def _name(d):
    n = d.get('label') or d.get('host') or d.get('vendor') or d['mac']
    return n.replace('.lan', '')

def wifi_lines(day=None):
    day = _day(day); lines = []
    try:
        import netscan
        ds = netscan.listing()['devices']; by = {d['mac']: d for d in ds}
        oldnames = {(d.get('host') or '').lower() for d in ds if not (d.get('first_seen') or '').startswith(day) and d.get('host')}
        new = [d for d in ds if (d.get('first_seen') or '').startswith(day)
               and not (d.get('host') and d['host'].lower() in oldnames)
               and 'random' not in (d.get('vendor') or '')        # phones/Macs rotate private MACs daily - not really new
               and 'dhileep' not in (d.get('host') or '').lower()]
        if new:
            new.sort(key=lambda d: d['first_seen'])
            lines.append(f"🆕 New devices on Wi-Fi today ({len(new)}): " + ', '.join(
                (f"{_name(d)} {d['first_seen'][11:16]}" + ('' if _name(d) == d['mac'] else f" [{d['mac']}]")) for d in new[:6])
                + (f" +{len(new) - 6} more" if len(new) > 6 else ''))
        top = sorted([d for d in ds if d.get('today_min', 0) > 0], key=lambda d: -d['today_min'])
        lines.append(f"📶 router: {sum(1 for d in ds if d.get('online'))} online now, {len(top)} seen today")
    except Exception: by = {}
    try:
        u = json.load(open(_wf(day))).get('mb', {})
        import wifishaper; lim = wifishaper._load()
        used = sorted([(mb, mac) for mac, mb in u.items() if mb >= 1], reverse=True)
        if used:
            lines.append('📡 Chinnu-Hotspot data: ' + ', '.join(
                f"{(lim.get(mac, {}).get('label') or _name(by.get(mac, {'mac': mac})))} "
                f"{(f'{mb / 1000:.1f} GB' if mb >= 1000 else f'{mb:.0f} MB')}" for mb, mac in used[:6]))
    except Exception: pass
    return lines

NAMES = {'chinnu-voice': 'Voice', 'wake': 'Wake word', 'pidog': 'PiDog body', 'net': 'Server internet/cable', 'openai': 'OpenAI',
         'tailscale': 'Tailscale', 'hotspot': 'Hotspot', 'hdd': 'Hard disk', 'chinnu-telegram': 'Telegram bot',
         'chinnu-alexa': 'Alexa bridge', 'cync2mqtt': 'Lights bridge', 'govee': 'Govee', 'strip': 'Power strip',
         'ollama': 'Local AI', 'chinnu-lan': 'Home app', 'self': 'Dashboard'}

def health_lines(day=None):
    day = _day(day); lines = []
    p = os.path.join(LOGS, f'uptime-{day}.jsonl'); rows = []
    if os.path.exists(p):
        for line in open(p):
            try: rows.append(json.loads(line))
            except Exception: pass
    if len(rows) >= 2:
        gaps = sorted(b['t'] - a['t'] for a, b in zip(rows, rows[1:]))
        step = min(gaps[len(gaps) // 2], 300)
        down = collections.Counter()
        for r in rows:
            for k, v in r.get('s', {}).items():
                if not v: down[k] += step / 60
        # time the server itself was not recording (e.g. no power) counts as a gap
        big = [(a['t'], b['t']) for a, b in zip(rows, rows[1:]) if b['t'] - a['t'] > 15 * 60]
        net = down.get('net', 0)
        NETDEP = {'wake', 'pidog', 'openai', 'govee', 'tailscale', 'strip', 'chinnu-alexa', 'cync2mqtt'}
        bad = [(m, k) for k, m in down.items() if m >= 5 and not (net >= 5 and k in NETDEP and m <= net + 10)]
        if bad:
            bad.sort(reverse=True)
            lines.append('🩺 Downtime: ' + ', '.join(f"{NAMES.get(k, k)} {_hm(m)}" for m, k in bad[:5]))
        else:
            lines.append('🩺 All features up all day ✅')
        if big:
            lines.append('⏸ Server not recording: ' + ', '.join(
                f"{time.strftime('%H:%M', time.localtime(a))}–{time.strftime('%H:%M', time.localtime(b))}" for a, b in big[:3]))
    al = _events(day, ('alert',))
    if al:
        c = collections.Counter(e.get('text', '').split(' (')[0][:60] for e in al)
        lines.append(f"⚠️ Alerts: {len(al)} — " + '; '.join(f"{t}{f' ×{n}' if n > 1 else ''}" for t, n in c.most_common(3)))
    return lines

def battery_extra(day=None):
    day = _day(day); n = 0; prev = None
    p = os.path.join(LOGS, f'battery-{day}.jsonl')
    if os.path.exists(p):
        for line in open(p):
            try: ch = json.loads(line).get('charging')
            except Exception: continue
            if ch and prev is False: n += 1
            prev = ch
    return n

def sections(day=None):
    out = []
    for fn in (presence_lines, wifi_lines, health_lines):
        try: out += fn(day)
        except Exception as e: out.append(f'({fn.__name__} error: {e})')
    return out
