"""Motion camera: whenever Chinnu's camera sees movement, take a photo AND record a 30 s video clip (mp4, same name).
- Photos: /mnt/hdd/chinnu/motion/YYYY-MM-DD/HHMMSS.jpg (kept 30 days), synced to Nextcloud /Chinnu/motion every 10 min.
- Telegram: photo sent when Chintu is AWAY (presence) or guard mode is on - or always if 'telegram' is set to 'always'.
- Ignores movement caused by Chinnu itself (robot busy / just did an action / whole frame shifted).
Settings in motioncam.json: {"on": true, "telegram": "away" | "always" | "off"}."""
import os, json, time, threading, shutil, pathlib, requests, subprocess
CLIP_SECS = 30
_rec = {'proc': None}

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(BASE, 'motioncam.json')
ROOT = pathlib.Path('/mnt/hdd/chinnu/motion')
KEEP_DAYS, GAP, TG_GAP = 30, 20, 120          # seconds between saved photos / Telegram photos
ROBOT = HDR = None
_st = {'last_photo': None, 'today': 0, 'note': 'starting'}

def cfg():
    try: return {'on': True, 'telegram': 'away', **json.load(open(CFG))}
    except Exception: return {'on': True, 'telegram': 'away'}

def set_cfg(**kw):
    c = cfg(); c.update({k: v for k, v in kw.items() if v is not None}); json.dump(c, open(CFG, 'w')); return status()

def _get(path, t=6):
    return requests.get(f'{ROBOT}{path}', headers=HDR, timeout=t)

def _robot_busy(prev_last):
    try:
        s = _get('/status', 3).json(); last = (s.get('last') or {})
        key = f"{last.get('name')}@{last.get('at')}"
        return bool(s.get('busy')) or (prev_last is not None and key != prev_last), key
    except Exception: return True, prev_last

def _away():
    try:
        import home_auto; return home_auto._load().get('presence') == 'away'
    except Exception: return False

def _guard_on():
    try:
        import behaviors; return behaviors.status().get('guard')
    except Exception: return False

def _save(jpg):
    d = ROOT / time.strftime('%Y-%m-%d'); d.mkdir(parents=True, exist_ok=True)
    p = d / time.strftime('%H%M%S.jpg'); p.write_bytes(jpg); return p

def _cleanup():
    cut = time.strftime('%Y-%m-%d', time.localtime(time.time() - KEEP_DAYS * 86400))
    for d in ROOT.glob('20*'):
        if d.name < cut: shutil.rmtree(d, ignore_errors=True)

def _sync():
    try:
        import nextcloud_sync; nextcloud_sync.sync_dir(str(ROOT / time.strftime('%Y-%m-%d')), sub='motion', exts=('.jpg', '.mp4'))
    except Exception as e: print('[motion] nextcloud', e, flush=True)

def _recording():
    p = _rec['proc']; return p is not None and p.poll() is None

def _start_clip(path):
    """Record CLIP_SECS of the robot camera into path (skipped if a clip is already running)."""
    if _recording(): return
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'mjpeg', '-r', '8', '-i', f'{ROBOT}/camera', '-t', str(CLIP_SECS),
           '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28', '-pix_fmt', 'yuv420p', '-r', '8', '-movflags', '+faststart', str(path)]
    try:
        _rec['proc'] = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _st['last_video'] = time.strftime('%I:%M:%S %p')
    except Exception as e: print('[motion] video', e, flush=True)

def _loop():
    import vision
    time.sleep(40)
    prev, last_key, quiet_until, t_save, t_tg, t_sync, t_clean = None, None, 0, 0, 0, time.time(), 0
    while True:
        try:
            c = cfg()
            if not c['on'] or _guard_on():              # guard mode has its own camera loop
                _st['note'] = 'off' if not c['on'] else 'guard mode is watching'; prev = None; time.sleep(5); continue
            busy, last_key = _robot_busy(last_key)
            if busy: quiet_until = time.time() + 4; prev = None
            r = _get('/snap.jpg'); jpg = r.content if r.ok and len(r.content) > 1000 else None
            if jpg and prev and time.time() > quiet_until:
                m = vision.motion(prev, jpg, min_frac=0.02)
                if m.get('moved') and m['frac'] < 0.6 and time.time() - t_save > GAP:
                    p = _save(jpg); t_save = time.time()
                    _start_clip(p.with_suffix('.mp4'))
                    _st.update(last_photo=time.strftime('%I:%M:%S %p'), today=len(list(p.parent.glob('*.jpg'))), note='watching')
                    mode = c['telegram']
                    if mode != 'off' and time.time() - t_tg > TG_GAP and (mode == 'always' or _away()):
                        import telegram_bot
                        telegram_bot.send_photo(jpg, f"📸 Motion at home — {time.strftime('%I:%M %p')}"); t_tg = time.time()
            prev = jpg or prev
            _st['note'] = _st['note'] if _st['note'] not in ('starting', 'off', 'guard mode is watching') else 'watching'
            if time.time() - t_sync > 600: _sync(); t_sync = time.time()
            if time.time() - t_clean > 86400: _cleanup(); t_clean = time.time()
        except Exception as e:
            print('[motion]', e, flush=True); time.sleep(5)
        time.sleep(1.5)

def status():
    d = ROOT / time.strftime('%Y-%m-%d')
    return {**cfg(), **_st, 'today': len(list(d.glob('*.jpg'))) if d.exists() else 0,
            'videos_today': len(list(d.glob('*.mp4'))) if d.exists() else 0, 'recording': _recording()}

def recent(n=12):
    out = []
    for d in sorted(ROOT.glob('20*'), reverse=True):
        for f in sorted(d.glob('*.jpg'), reverse=True):
            v = f.with_suffix('.mp4')
            out.append({'day': d.name, 'file': f.name, 't': f'{f.name[:2]}:{f.name[2:4]}:{f.name[4:6]}',
                        'video': v.name if v.exists() and not (_recording() and time.time() - v.stat().st_mtime < 3) else None})
            if len(out) >= n: return out
    return out

def image(day, file):
    p = (ROOT / day / file).resolve()
    if ROOT.resolve() in p.parents and p.suffix == '.jpg' and p.exists(): return p.read_bytes()
    return None

def start(robot, hdr):
    global ROBOT, HDR
    ROBOT, HDR = robot, hdr
    threading.Thread(target=_loop, daemon=True).start()
