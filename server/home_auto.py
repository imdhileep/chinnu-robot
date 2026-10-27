"""Home automations (runs in the dashboard): presence (auto home/away), quiet hours, Blink door alerts,
morning briefing, nightly diary. Settings: config.yaml -> home_auto."""
import os, json, time, threading, subprocess, yaml, requests
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(BASE, 'home_auto.json')
ROBOT = HDR = None
_st = {}

def cfg():
    c = (yaml.safe_load(open(os.path.join(BASE, 'config.yaml'), encoding='utf-8-sig')) or {}).get('home_auto') or {}
    return {'owner_macs': [m.lower() for m in (c.get('owner_macs') or [])], 'away_min': float(c.get('away_min', 10)),
            'quiet_start': str(c.get('quiet_start', '23:00')), 'quiet_end': str(c.get('quiet_end', '07:00')),
            'quiet_volume': int(c.get('quiet_volume', 20)), 'day_volume': int(c.get('day_volume', 70)),
            'briefing_at': str(c.get('briefing_at', '07:00')), 'diary_at': str(c.get('diary_at', '22:05')),
            'door_alerts': c.get('door_alerts', True)}

def _load():
    try: return json.load(open(STATE))
    except Exception: return {}
def _save(s): json.dump(s, open(STATE, 'w'), indent=1)

def tg(msg, photo=None):
    try:
        import telegram_bot
        telegram_bot.send_photo(photo, msg) if photo else telegram_bot.send(msg)
    except Exception as e: print('[home] tg', e, flush=True)

def hlog(kind, msg):
    try:
        import history; history.log(kind, msg)
    except Exception: pass

def quiet_now():
    c = cfg(); n = time.strftime('%H:%M')
    s, e = c['quiet_start'], c['quiet_end']
    return (s <= n or n < e) if s > e else (s <= n < e)

def say(text):
    """Proactive speech - skipped during quiet hours (Telegram still gets the message)."""
    if quiet_now(): return False
    try:
        import voice; threading.Thread(target=voice.say, args=(text,), daemon=True).start(); return True
    except Exception: return False

def run_routine(name):
    try:
        import commands
        r = commands.run(name)
        if r.get('say'): say(r['say'])
        return r
    except Exception as e:
        print('[home] routine', e, flush=True); return {}

# ---------------- 1. presence ----------------
def _seen(mac):
    try:
        import netscan
        ip = netscan._load()['devices'].get(mac, {}).get('ip')
    except Exception: ip = None
    if not ip: return False
    subprocess.run(['ping', '-c', '1', '-W', '1', ip], capture_output=True)
    out = subprocess.run(['ip', 'neigh', 'show', ip], capture_output=True, text=True).stdout.lower()
    return mac in out and any(k in out for k in ('reachable', 'delay', 'probe', 'stale'))

def presence():
    c = cfg()
    if not c['owner_macs']: return
    s = _load(); now = time.time()
    if any(_seen(m) for m in c['owner_macs']):
        s['last_seen'] = now
        if s.get('presence') == 'away':
            s['presence'] = 'home'; _save(s)
            hlog('presence', 'Chintu came home (phone on Wi-Fi)'); tg('🏠 Welcome home! Guard mode off.')
            run_routine('auto home'); return
        s.setdefault('presence', 'home')
    elif s.get('presence') == 'home' and now - s.get('last_seen', now) > c['away_min'] * 60:
        s['presence'] = 'away'; _save(s)
        hlog('presence', 'Chintu left (phone off Wi-Fi)'); tg('🚪 You left home. Guard mode on (lights/TV untouched).')
        run_routine('auto away'); return
    _save(s)

# ---------------- 2. quiet hours (volume) ----------------
def quiet_volume():
    c = cfg(); s = _load(); q = quiet_now()
    if q != s.get('quiet'):
        try:
            requests.post(f'{ROBOT}/volume', headers=HDR, params={'percent': c['quiet_volume'] if q else c['day_volume']}, timeout=5)
        except Exception: pass
        s['quiet'] = q; _save(s); hlog('quiet', 'quiet hours ' + ('start' if q else 'end'))

# ---------------- 3. Blink door alerts ----------------
def door_alerts():
    if not cfg()['door_alerts']: return
    try:
        import blink_tool
        cams = blink_tool.cameras(max_age=60)
    except Exception as e:
        print('[home] blink', str(e)[:100], flush=True); return
    s = _load(); seen = s.setdefault('blink_last', {})
    for cam in cams:
        n, rec = cam['name'], cam.get('last_record')
        if not rec: continue
        if n not in seen: seen[n] = rec; continue          # first run: remember, don't alert
        if rec != seen[n]:
            seen[n] = rec
            photo = None
            try: _, photo = blink_tool.snapshot(n)
            except Exception: pass
            where = 'main door' if 'door' in n.lower() or 'front' in n.lower() else n
            tg(f'🚪 Motion at {where} ({time.strftime("%I:%M %p")})', photo)
            hlog('alert', f'motion at {where}')
            say(f'Anna, {where} daggara evaro unnaru.')
    _save(s)

# ---------------- 4. morning briefing ----------------
def briefing_text():
    import extras
    w = extras.weather(); nw = extras.news(limit=3)
    lines = [f'☀️ Good morning Chintu! {datetime.now():%A, %d %B}']
    if w.get('ok'):
        t = w['today']
        lines.append(f"🌤 Now {w['now_f']:.0f}°F (feels {w['feels_f']:.0f}°F), {w['sky']}. Today {t['low_f']:.0f}–{t['high_f']:.0f}°F, rain {t['rain_chance']}%.")
        if t['rain_chance'] >= 50: lines.append('☔ Take an umbrella today.')
        if t['low_f'] <= 35: lines.append('🥶 Freezing this morning - dress warm.')
    if nw.get('ok'):
        lines.append('📰 ' + ' | '.join(h['title'].split(' - ')[0][:90] for h in nw['headlines'][:3]))
    try:
        b = requests.get(f'{ROBOT}/battery', headers=HDR, timeout=5).json()
        lines.append(f"🔋 Chinnu battery {b.get('percent')}%")
    except Exception: lines.append('🔋 Chinnu body offline')
    try:
        import ops; lines.append(f"💰 OpenAI this month ${ops.month_usd():.2f}" + (' · saver mode ON' if ops.saver_on() else ''))
    except Exception: pass
    try:
        import history
        night = [r for r in history.read(limit=400) if r['kind'] == 'alert' and r['t'] < '07:30']
        if night: lines.append(f"⚠️ {len(night)} alert(s) overnight - last: {night[-1]['text'][:80]}")
    except Exception: pass
    return '\n'.join(lines)

# ---------------- 5. diary ----------------
def diary_text():
    import history
    t = history.summary_text()
    return ('🧠 Chinnu diary — ' + time.strftime('%d %b') + '\n' + t) if t else None

# ---------------- loop ----------------
def _daily(key, at):
    s = _load(); today = time.strftime('%Y-%m-%d')
    if time.strftime('%H:%M') >= at and s.get(key) != today:
        s[key] = today; _save(s); return True
    return False

def _loop():
    time.sleep(30); t_door = 0
    s = _load(); today = time.strftime('%Y-%m-%d'); c = cfg()
    for k, at in (('briefing_day', c['briefing_at']), ('diary_day', c['diary_at'])):   # don't fire for a time already passed today
        if time.strftime('%H:%M') >= at: s[k] = today
    _save(s)
    while True:
        try:
            c = cfg()
            presence(); quiet_volume()
            if time.time() - t_door > 90: door_alerts(); t_door = time.time()
            if _daily('briefing_day', c['briefing_at']): tg(briefing_text())
            _daily('diary_day', c['diary_at'])   # diary is now part of the nightly report (ops.report_text)
        except Exception as e:
            print('[home]', e, flush=True)
        time.sleep(60)

def status():
    s = _load(); c = cfg()
    return {'presence': s.get('presence', 'unknown' if c['owner_macs'] else 'not set up'), 'quiet_now': quiet_now(),
            'config': c, 'blink_seen': list((s.get('blink_last') or {}).keys())}

def start(robot, hdr):
    global ROBOT, HDR
    ROBOT, HDR = robot, hdr
    threading.Thread(target=_loop, daemon=True).start()
