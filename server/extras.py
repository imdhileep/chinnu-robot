"""Chinnu extras: long-term memory, reminders, weather/time. Used by brain.py (tools) and voice_agent.py (reminder thread)."""
import os, json, time, threading, requests
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
MEM_FILE = os.path.join(BASE, 'memory.json')
REM_FILE = os.path.join(BASE, 'reminders.json')
_lock = threading.Lock()
LAT, LON, PLACE = 38.98, -94.67, 'Overland Park'

def _load(p, default):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return default

def _save(p, data):
    tmp = p + '.tmp'; json.dump(data, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); os.replace(tmp, p)

# ---------------- memory ----------------
def remember(text):
    text = (text or '').strip()
    if not text: return {'ok': False, 'error': 'empty'}
    with _lock:
        m = _load(MEM_FILE, {'facts': []})
        if any(f['text'].lower() == text.lower() for f in m['facts']):
            return {'ok': True, 'note': 'already known'}
        m['facts'].append({'text': text, 'at': time.strftime('%Y-%m-%d %H:%M')})
        m['facts'] = m['facts'][-200:]
        _save(MEM_FILE, m)
    return {'ok': True, 'count': len(m['facts'])}

def forget(text):
    q = (text or '').strip().lower()
    with _lock:
        m = _load(MEM_FILE, {'facts': []})
        keep = [f for f in m['facts'] if q not in f['text'].lower()]
        removed = len(m['facts']) - len(keep)
        m['facts'] = keep; _save(MEM_FILE, m)
    return {'ok': True, 'removed': removed}

def facts():
    return _load(MEM_FILE, {'facts': []})['facts']

def memory_block():
    f = facts()
    if not f: return ''
    return '\nTHINGS CHINTU TOLD YOU TO REMEMBER (use when relevant):\n' + '\n'.join(f"- {x['text']} ({x['at']})" for x in f[-60:])

# ---------------- reminders ----------------
def _parse_when(minutes=None, at=None):
    now = datetime.now()
    if minutes:
        return now + timedelta(minutes=float(minutes))
    if at:
        at = str(at).strip().lower().replace('.', ':')
        try:
            if ' ' in at:  # "YYYY-MM-DD HH:MM"
                return datetime.strptime(at, '%Y-%m-%d %H:%M')
            hh, mm = at.replace('am', '').replace('pm', '').strip().split(':')
            hh, mm = int(hh), int(mm)
            if 'pm' in at and hh < 12: hh += 12
            if 'am' in at and hh == 12: hh = 0
            t = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if t <= now: t += timedelta(days=1)
            return t
        except Exception:
            return None
    return None

def set_reminder(text, minutes=None, at=None):
    when = _parse_when(minutes, at)
    if not when: return {'ok': False, 'error': 'give minutes (number) or at (HH:MM)'}
    with _lock:
        r = _load(REM_FILE, [])
        rid = int(time.time() * 1000) % 100000000
        r.append({'id': rid, 'text': text, 'when': when.strftime('%Y-%m-%d %H:%M'), 'done': False})
        _save(REM_FILE, r)
    return {'ok': True, 'id': rid, 'when': when.strftime('%a %H:%M'), 'in_minutes': round((when - datetime.now()).total_seconds() / 60)}

def list_reminders():
    r = [x for x in _load(REM_FILE, []) if not x['done']]
    return {'ok': True, 'reminders': [{'id': x['id'], 'text': x['text'], 'when': x['when']} for x in r]}

def cancel_reminder(rid=None, text=None):
    with _lock:
        r = _load(REM_FILE, []); n = 0
        for x in r:
            if x['done']: continue
            if (rid and x['id'] == int(rid)) or (text and str(text).lower() in x['text'].lower()):
                x['done'] = True; n += 1
        _save(REM_FILE, r)
    return {'ok': True, 'cancelled': n}

def due_reminders():
    """Pop reminders whose time has come (called by the voice agent loop)."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    out = []
    with _lock:
        r = _load(REM_FILE, [])
        for x in r:
            if not x['done'] and x['when'] <= now:
                x['done'] = True; out.append(x)
        if out:
            r = [x for x in r if not x['done'] or x['when'] > (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M')]
            _save(REM_FILE, r)
    return out

# ---------------- weather / time ----------------
_WCODES = {0: 'clear sky', 1: 'mostly clear', 2: 'partly cloudy', 3: 'overcast', 45: 'fog', 48: 'fog', 51: 'light drizzle', 53: 'drizzle', 55: 'heavy drizzle',
           61: 'light rain', 63: 'rain', 65: 'heavy rain', 71: 'light snow', 73: 'snow', 75: 'heavy snow', 80: 'rain showers', 81: 'rain showers', 82: 'heavy showers',
           95: 'thunderstorm', 96: 'thunderstorm with hail', 99: 'thunderstorm with hail'}

def weather():
    try:
        u = (f'https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current=temperature_2m,apparent_temperature,'
             f'relative_humidity_2m,weather_code,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code'
             f'&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=America%2FChicago&forecast_days=2')
        d = requests.get(u, timeout=10).json()
        c = d['current']; dy = d['daily']
        return {'ok': True, 'place': PLACE, 'now_f': c['temperature_2m'], 'feels_f': c['apparent_temperature'], 'humidity': c['relative_humidity_2m'],
                'wind_mph': c['wind_speed_10m'], 'sky': _WCODES.get(c['weather_code'], 'unknown'),
                'today': {'high_f': dy['temperature_2m_max'][0], 'low_f': dy['temperature_2m_min'][0], 'rain_chance': dy['precipitation_probability_max'][0], 'sky': _WCODES.get(dy['weather_code'][0], '')},
                'tomorrow': {'high_f': dy['temperature_2m_max'][1], 'low_f': dy['temperature_2m_min'][1], 'rain_chance': dy['precipitation_probability_max'][1], 'sky': _WCODES.get(dy['weather_code'][1], '')}}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def now_info():
    n = datetime.now()
    return {'ok': True, 'time': n.strftime('%I:%M %p'), 'date': n.strftime('%A, %d %B %Y'), 'tz': 'America/Chicago (Overland Park)'}

# ---------------- news (Google News RSS, no key) ----------------
def news(topic=None, lang="en", limit=6):
    import xml.etree.ElementTree as ET, urllib.parse
    try:
        if lang == "te":
            base = "https://news.google.com/rss?hl=te&gl=IN&ceid=IN:te"
        else:
            base = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
        if topic:
            q = urllib.parse.quote(topic)
            hl, gl, ceid = ("te", "IN", "IN:te") if lang == "te" else ("en-US", "US", "US:en")
            base = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
        r = requests.get(base, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(r.content)
        items = []
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            src = it.find("source"); src = src.text if src is not None else ""
            if title: items.append({"title": title, "source": src})
            if len(items) >= limit: break
        return {"ok": True, "topic": topic or "top", "lang": lang, "headlines": items}
    except Exception as e:
        return {"ok": False, "error": str(e)}
