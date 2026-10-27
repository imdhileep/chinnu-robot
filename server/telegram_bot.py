"""Chinnu Telegram bot: phone alerts + remote commands from anywhere (no VPN needed).
Token: TELEGRAM_TOKEN in ~/chinnu-agent/.env. The first person to send /start becomes the owner;
only the owner's chat is served (stored in telegram_owner.json)."""
import os, json, time, threading, requests
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

TOKEN = os.environ.get('TELEGRAM_TOKEN', '').strip()
API = f'https://api.telegram.org/bot{TOKEN}'
DASH = 'http://127.0.0.1:8080'
CHATSRV = 'http://127.0.0.1:8081/chat'
OWNER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'telegram_owner.json')
LOW_BAT_V = 7.0

owner = None
if os.path.exists(OWNER_FILE):
    try: owner = json.load(open(OWNER_FILE)).get('chat_id')
    except Exception: pass

def tg(method, **kw):
    try:
        r = requests.post(f'{API}/{method}', json=kw, timeout=30)
        return r.json()
    except Exception as e:
        print('[tg]', method, e, flush=True); return {}

def send(text, chat_id=None):
    cid = chat_id or owner
    if cid: tg('sendMessage', chat_id=cid, text=text)

def send_photo(jpg, caption='', chat_id=None):
    cid = chat_id or owner
    if not cid: return
    try:
        requests.post(f'{API}/sendPhoto', data={'chat_id': cid, 'caption': caption}, files={'photo': ('snap.jpg', jpg, 'image/jpeg')}, timeout=30)
    except Exception as e:
        print('[tg] photo', e, flush=True)

def api(method, path, **kw):
    try:
        r = requests.request(method, DASH + path, timeout=kw.pop('timeout', 25), **kw)
        return r.json() if r.headers.get('content-type', '').startswith('application/json') else r.content
    except Exception as e:
        return {'ok': False, 'error': str(e)}

HELP = """Chinnu bot commands:
/status - PiDog + server status
/photo - camera snapshot\n/who - who is in front of Chinnu (face recognition)
/blink [main door|patio] - home camera snapshot (default both)
/look [question] - Chinnu describes what it sees
/sit /stand /lie /stop /wag /stretch
/lights on|off|<1-100> - room (fan) lights
/desk on|off|<1-100> - desk lamp
/cmd <name> - run routine (movie mode, good night, ...)
/say <text> - Chinnu speaks it at home
/mute /unmute
/restart - restart PiDog controller
Anything else you type -> Chinnu brain (reply here, not spoken)"""

def status_text():
    s = api('GET', '/api/state'); v = api('GET', '/api/server')
    bat = s.get('battery') or {}
    return (f"PiDog: {'online' if s.get('robot_ok') else 'OFFLINE'} | mode {s.get('mode')}\n"
            f"Battery: {bat.get('percent', '?')}% ({bat.get('voltage', '?')}V)\n"
            f"Server: {v.get('temp')} temp, up {v.get('uptime')}, load {v.get('load')}\n"
            f"Services: " + ', '.join(f"{k.replace('chinnu-', '')}={x}" for k, x in (v.get('services') or {}).items()))

def handle(chat_id, text):
    global owner
    t = text.strip(); low = t.lower()
    if low.startswith('/start'):
        if owner is None:
            owner = chat_id; json.dump({'chat_id': chat_id}, open(OWNER_FILE, 'w'))
            send("Namaste anna! Nenu Chinnu bot. Alerts ikkada vastayi. /help chudu.", chat_id); return
    if chat_id != owner:
        tg('sendMessage', chat_id=chat_id, text='Sorry, this bot is private.'); return
    if low in ('/help', 'help'): send(HELP); return
    if low.startswith('/status'): send(status_text()); return
    if low.startswith('/photo'):
        jpg = api('GET', '/api/snap')
        if isinstance(jpg, (bytes, bytearray)) and len(jpg) > 1000: send_photo(jpg, time.strftime('%H:%M:%S'))
        else: send('Camera not available.')
        return
    if low.startswith('/blink') or low.startswith('/door') or low.startswith('/patio'):
        arg = t.split(maxsplit=1)[1].strip().lower() if ' ' in t else ('patio' if low.startswith('/patio') else 'main door' if low.startswith('/door') else '')
        cams = [arg] if arg else ['main door', 'patio']
        send('Blink snapshot... (~15 s)')
        for c in cams:
            try:
                r = requests.get(f'{DASH}/api/blink/{c}.jpg', timeout=90)
                if r.ok and len(r.content) > 1000: send_photo(r.content, f"{r.headers.get('X-Camera', c)} {time.strftime('%H:%M:%S')}")
                else: send(f'{c}: not available ({r.text[:100]})')
            except Exception as e: send(f'{c}: error {e}')
        return
    if low.startswith('/who'):
        r = api('GET', '/api/faces/identify')
        fs = r.get('faces') if isinstance(r, dict) else None
        send('Nobody visible.' if not fs else ', '.join(f"{f['name'] or 'unknown'} ({f['pos']}, {f['score']})" for f in fs)); return
    if low.startswith('/look'):
        q = t[5:].strip() or 'What do you see?'
        send('Looking...')
        r = requests.post(CHATSRV, json={'text': f'(Use the look tool and answer) {q}', 'speak': False}, timeout=120).json()
        send(r.get('reply') or str(r)); return
    for c in ('sit', 'stand', 'lie', 'stop', 'stretch'):
        if low == '/' + c:
            r = api('POST', f'/api/action/{c}'); send('ok' if r.get('ok') else f'failed: {r}'); return
    if low == '/wag': r = api('POST', '/api/action/wag_tail'); send('ok' if r.get('ok') else f'failed: {r}'); return
    if low.startswith('/lights') or low.startswith('/desk'):
        grp = 'room' if low.startswith('/lights') else 'desk'
        arg = t.split(maxsplit=1)[1].strip().lower() if ' ' in t else 'on'
        if arg in ('on', 'off'): r = api('POST', f'/api/light/{grp}/{arg}')
        elif arg.isdigit(): r = api('POST', f'/api/light/{grp}/brightness?value={int(arg)}')
        else: send('usage: /lights on|off|<1-100>'); return
        send('ok' if r.get('ok') else f'failed: {r}'); return
    if low.startswith('/cmd '):
        r = api('POST', '/api/cmd/' + requests.utils.quote(t[5:].strip())); send(r.get('say') or ('ok' if r.get('ok') else f'failed: {r.get("error", r)}')); return
    if low.startswith('/say '):
        r = requests.post(CHATSRV, json={'text': f'Say exactly this out loud and nothing else: "{t[5:].strip()}"', 'speak': True}, timeout=120).json()
        send('said: ' + (r.get('reply') or '')); return
    if low == '/mute': api('POST', '/api/volume?mute=on'); send('muted'); return
    if low == '/unmute': api('POST', '/api/volume?mute=off'); send('unmuted'); return
    if low == '/restart': r = api('POST', '/api/robot/restart', timeout=60); send('controller restarting (~1 min)'); return
    if low.startswith('/'): send(HELP); return
    # free text -> brain (text reply only)
    try:
        r = requests.post(CHATSRV, json={'text': t, 'speak': False}, timeout=120).json()
        send(r.get('reply') or str(r))
    except Exception as e:
        send(f'brain offline: {e}')

def alerts_thread():
    """Watch PiDog/server health and push alerts."""
    last_ok = None; offline_since = None; warned_off = False; bat_warned = 0; svc_bad = {}
    time.sleep(10)
    while True:
        try:
            s = api('GET', '/api/state')
            ok = bool(s.get('robot_ok'))
            if ok != last_ok and last_ok is not None:
                if not ok: offline_since = time.time(); warned_off = False
                else:
                    if warned_off: send('PiDog is back online.')
                    offline_since = None
            if not ok and offline_since and not warned_off and time.time() - offline_since > 90:
                send('ALERT: PiDog offline for 90s (battery/Wi-Fi/hang?).'); warned_off = True
            last_ok = ok
            bat = s.get('battery') or {}
            v = bat.get('voltage')
            if v and v < LOW_BAT_V and time.time() - bat_warned > 3600:
                bat_warned = time.time(); send(f'ALERT: PiDog battery low: {bat.get("percent")}% ({v}V). Charge it.')
            srv = api('GET', '/api/server')
            for name, st in (srv.get('services') or {}).items():
                if name == 'chinnu-display-keepalive': continue
                if st != 'active' and not svc_bad.get(name):
                    svc_bad[name] = True; send(f'ALERT: service {name} is {st}.')
                elif st == 'active' and svc_bad.get(name):
                    svc_bad[name] = False; send(f'{name} is active again.')
            try:
                temp = float(str(srv.get('temp', '0')).replace("'C", ''))
                if temp > 78 and time.time() - bat_warned > 1800: send(f'ALERT: server temp {temp}C')
            except Exception: pass
        except Exception as e:
            print('[alerts]', e, flush=True)
        time.sleep(15)

def notify_thread():
    """Forward dashboard notifications (reminders, schedules) to the phone."""
    since = time.time()
    while True:
        try:
            for n in api('GET', f'/api/notify?since={since}') or []:
                since = max(since, n['at']); send(n['text'])
        except Exception as e:
            print('[notify]', e, flush=True)
        time.sleep(10)

def main():
    if not TOKEN:
        print('TELEGRAM_TOKEN missing in .env', flush=True); return
    me = tg('getMe'); print('bot:', me.get('result', {}).get('username'), 'owner:', owner, flush=True)
    threading.Thread(target=alerts_thread, daemon=True).start()
    threading.Thread(target=notify_thread, daemon=True).start()
    if owner: send('Chinnu bot started.')
    offset = None
    while True:
        try:
            r = requests.get(f'{API}/getUpdates', params={'timeout': 50, 'offset': offset}, timeout=60).json()
            for u in r.get('result', []):
                offset = u['update_id'] + 1
                m = u.get('message') or {}
                if m.get('text'):
                    threading.Thread(target=handle, args=(m['chat']['id'], m['text']), daemon=True).start()
        except Exception as e:
            print('[poll]', e, flush=True); time.sleep(5)

if __name__ == '__main__':
    main()
