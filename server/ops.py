"""Chinnu ops (runs inside the dashboard): budget guard, nightly Telegram report, battery log, auto-heal.
Settings in config.yaml -> ops: {daily_usd, monthly_usd, report_at, heal}."""
import os, json, time, threading, subprocess, glob, requests, yaml

BASE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(BASE, 'logs')
SAVER = os.path.join(BASE, 'saver_mode.json')
ROBOT = HDR = None
_state = {'warned': {}, 'heal': {}, 'report_day': None}

def cfg():
    c = (yaml.safe_load(open(os.path.join(BASE, 'config.yaml'), encoding='utf-8-sig')) or {}).get('ops') or {}
    return {'daily_usd': float(c.get('daily_usd', 2.0)), 'monthly_usd': float(c.get('monthly_usd', 30.0)),
            'report_at': str(c.get('report_at', '22:00')), 'heal': c.get('heal', True)}

def tg(msg):
    try:
        import telegram_bot; telegram_bot.send(msg)
    except Exception as e: print('[ops] telegram', e, flush=True)

def hlog(kind, msg):
    try:
        import history; history.log(kind, msg)
    except Exception: pass

# ---------------- 1. budget guard ----------------
def saver_on(): return os.path.exists(SAVER)

def set_saver(on, why=''):
    if on and not saver_on():
        json.dump({'since': time.strftime('%Y-%m-%d %H:%M'), 'why': why}, open(SAVER, 'w'))
        tg(f'💰 Chinnu saver mode ON ({why}). Small talk uses the cheaper model, realtime voice is paused until tomorrow. Say "saver mode off" or use the Server page to override.')
        hlog('alert', f'saver mode on: {why}')
    elif not on and saver_on():
        os.remove(SAVER); hlog('alert', 'saver mode off')

def month_usd():
    import usage
    m = time.strftime('%Y-%m')
    return round(sum(usage.summary(os.path.basename(p)[6:16])['usd'] for p in glob.glob(os.path.join(LOGS, f'usage-{m}-*.jsonl'))), 2)

def budget_check():
    import usage
    c = cfg(); today = time.strftime('%Y-%m-%d')
    d = usage.summary()['usd']; m = month_usd()
    if saver_on():
        s = json.load(open(SAVER))
        if s.get('since', '')[:10] != today and d < c['daily_usd'] * 0.8 and m < c['monthly_usd']:
            set_saver(False)                     # new day -> back to normal
    for name, val, lim in (('daily', d, c['daily_usd']), ('monthly', m, c['monthly_usd'])):
        key = f'{name}-{today if name == "daily" else today[:7]}'
        if val >= 0.8 * lim and _state['warned'].get(key) is None:
            _state['warned'][key] = 80
            tg(f'⚠️ Chinnu OpenAI spend: {name} ${val:.2f} of ${lim:.2f} limit (80%).')
        if val >= lim:
            set_saver(True, f'{name} limit ${lim:.2f} reached (${val:.2f})')
    return {'today': d, 'month': m, 'limits': c, 'saver': saver_on()}

# ---------------- 3. battery log ----------------
def battery_log():
    try:
        b = requests.get(f'{ROBOT}/battery', headers=HDR, timeout=5).json()
    except Exception:
        b = {'voltage': None, 'percent': None}
    try:
        st = json.load(open(os.path.join(BASE, 'autocharge.json')))
        ch = st.get('charger_on')
    except Exception: ch = None
    rec = {'t': time.strftime('%H:%M'), 'v': b.get('voltage'), 'pct': b.get('percent'), 'charging': ch}
    with open(os.path.join(LOGS, time.strftime('battery-%Y-%m-%d.jsonl')), 'a') as f: f.write(json.dumps(rec) + '\n')

def battery_series(day=None):
    p = os.path.join(LOGS, f'battery-{day or time.strftime("%Y-%m-%d")}.jsonl')
    out = []
    if os.path.exists(p):
        for line in open(p):
            try: out.append(json.loads(line))
            except Exception: pass
    return out

# ---------------- 4. auto-heal ----------------
UNITS = ['chinnu-voice', 'chinnu-telegram', 'chinnu-lan', 'chinnu-alexa', 'chinnu-display-keepalive']
CONTS = ['nextcloud-db-1', 'nextcloud-redis-1', 'nextcloud-app-1', 'jellyfin', 'ollama']

def heal():
    if not cfg()['heal']: return
    now = time.time()
    def allowed(name):
        h = [t for t in _state['heal'].get(name, []) if now - t < 3600]
        _state['heal'][name] = h
        return len(h) < 3
    for u in UNITS:
        st = subprocess.run(['systemctl', 'is-active', u], capture_output=True, text=True).stdout.strip()
        if st in ('failed', 'inactive') and allowed(u):
            subprocess.run(['sudo', '-n', 'systemctl', 'restart', u], capture_output=True, timeout=60)
            _state['heal'][u].append(now)
            ok = subprocess.run(['systemctl', 'is-active', u], capture_output=True, text=True).stdout.strip()
            tg(f'🛠 Auto-heal: {u} was {st} → restarted ({ok}).'); hlog('alert', f'auto-heal {u}: {st} -> {ok}')
    if subprocess.run(['findmnt', '/mnt/hdd'], capture_output=True).returncode != 0:
        return                                   # hddwatch handles the disk + its containers
    ps = subprocess.run(['docker', 'ps', '-a', '--format', '{{.Names}}|{{.State}}'], capture_output=True, text=True).stdout
    for line in ps.splitlines():
        n, st = (line.split('|') + [''])[:2]
        if n in CONTS and st in ('exited', 'dead') and allowed(n):
            subprocess.run(['docker', 'start', n], capture_output=True, timeout=90)
            _state['heal'][n].append(now)
            tg(f'🛠 Auto-heal: container {n} was {st} → started.'); hlog('alert', f'auto-heal container {n}')

# ---------------- 2. nightly report ----------------
def report_text(day=None):
    import usage, srvpage
    day = day or time.strftime('%Y-%m-%d')
    u = usage.summary(day); dv = srvpage.srv_devices(day)
    lines = [f'🐕 Chinnu daily report — {day}', '']
    try:
        import history; dsum = history.summary_text(day)
        if dsum: lines += ['🧠 ' + dsum, '']
    except Exception: pass
    try:
        import nightly; lines += nightly.sections(day) + ['']
    except Exception as e: lines.append(f'(nightly error: {e})')
    used = [d for d in dv['devices'] if d['on_minutes'] or d['switches']]
    if used:
        lines.append('💡 Lights & plugs:')
        for d in sorted(used, key=lambda x: -x['on_minutes'])[:10]:
            lines.append(f"  • {d['device']}: on {d['on_minutes'] // 60}h {d['on_minutes'] % 60}m, {d['switches']} switches")
    ev = dv['events']
    guard = [e for e in ev if e.get('kind') == 'guard' and '🚨' in e.get('text', '')]
    alerts = [e for e in ev if e.get('kind') == 'alert']
    lines.append(f"🛡 Guard alerts: {len(guard)}" + (f" (last {guard[0]['t']})" if guard else ''))
    lines.append(f"💰 OpenAI (est.): ${u['usd']:.2f} today · ${month_usd():.2f} this month · {u['realtime_turns']} voice turns")
    bs = [b for b in battery_series(day) if b.get('pct') is not None]
    if bs: lines.append(f"🔋 PiDog battery: now {bs[-1]['pct']}% (low {min(b['pct'] for b in bs)}%, high {max(b['pct'] for b in bs)}%)" + (lambda n: f', charged {n}×' if n else '')(__import__('nightly').battery_extra(day)))
    disk = subprocess.run(['sh', '-c', "df -h /mnt/hdd | awk 'NR==2{print $5}'"], capture_output=True, text=True).stdout.strip()
    temp = subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True, text=True).stdout.strip().replace('temp=', '')
    lines.append(f"🖥 Server {temp}, hard disk {disk} used" + (f", {len(alerts)} alerts" if alerts else ''))
    try:
        pass
    except Exception: pass
    if saver_on(): lines.append('💰 Saver mode is ON')
    return '\n'.join(lines)

# ---------------- loop ----------------
def _loop():
    time.sleep(45); t_bat = t_bud = 0
    while True:
        now = time.time()
        try:
            if now - t_bud > 300: budget_check(); t_bud = now
            if now - t_bat > 600: battery_log(); t_bat = now
            heal()
            c = cfg()
            if time.strftime('%H:%M') >= c['report_at'] and _state['report_day'] != time.strftime('%Y-%m-%d'):
                _state['report_day'] = time.strftime('%Y-%m-%d'); tg(report_text())
        except Exception as e:
            print('[ops]', e, flush=True)
        time.sleep(60)

def start(robot, hdr):
    global ROBOT, HDR
    ROBOT, HDR = robot, hdr
    _state['report_day'] = time.strftime('%Y-%m-%d') if time.strftime('%H:%M') >= cfg()['report_at'] else None
    threading.Thread(target=_loop, daemon=True).start()
