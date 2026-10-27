"""Chinnu behaviours that use the camera + YOLO (vision.py):
  GUARD  - sit still, watch for motion; if a person appears who is not Chintu, send a photo to Telegram.
  FOLLOW - walk after the nearest person, keeping them centred, stop when close; give up if lost.
Run inside the dashboard process (one instance). Controlled via /api/guard/* and /api/follow/*."""
import time, threading, requests, os

ROBOT = HDR = None
_state = {'guard': False, 'follow': False, 'guard_note': '', 'follow_note': '', 'alerts': 0, 'last_alert': None}
_lock = threading.Lock()

def init(robot, hdr):
    global ROBOT, HDR
    ROBOT, HDR = robot, hdr

def status(): return dict(_state)

def _snap():
    try:
        r = requests.get(f'{ROBOT}/snap.jpg', headers=HDR, timeout=6)
        return r.content if r.ok and len(r.content) > 1000 else None
    except Exception: return None

def _post(path, **params):
    try: return requests.post(f'{ROBOT}{path}', headers=HDR, params=params, timeout=6).json()
    except Exception as e: return {'ok': False, 'error': str(e)}

def _say(text):
    try:
        import home_auto
        if home_auto.quiet_now(): return
    except Exception: pass
    try:
        import voice; threading.Thread(target=voice.say, args=(text,), daemon=True).start()
    except Exception: pass

def _log(kind, msg):
    print(f'[{kind}]', msg, flush=True)
    try:
        import history; history.log(kind, msg)
    except Exception: pass

def _telegram_photo(jpg, caption):
    try:
        import telegram_bot
        telegram_bot.send_photo(jpg, caption)
        return True
    except Exception as e:
        print('[guard] telegram', e, flush=True); return False

# ---------------- GUARD ----------------
def _guard_loop():
    import vision, faces
    _post('/action/sit'); time.sleep(1.5); _post('/head', yaw=0, roll=0, pitch=10)
    prev = None; cooldown = 0; quiet_since = time.time()
    _state['guard_note'] = 'watching'
    while _state['guard']:
        jpg = _snap()
        if not jpg: time.sleep(2); continue
        if prev is not None:
            m = vision.motion(prev, jpg)
            if m.get('moved'):
                people = vision.detect(jpg, only={'person'})
                if people:
                    f = faces.identify(jpg)
                    if 'Chintu' in (f.get('known') or []):
                        _state['guard_note'] = 'Chintu came home - guard off'
                        _log('guard', 'Chintu recognised - guard mode off')
                        _say('Welcome back anna! Guard mode off chesanu.')
                        _state['guard'] = False; break
                    if time.time() > cooldown:
                        who = ', '.join(f.get('known') or []) or 'unknown person'
                        cap = f'🚨 Chinnu guard: {who} seen at home ({time.strftime("%I:%M %p")}).'
                        _telegram_photo(jpg, cap)
                        _state['alerts'] += 1; _state['last_alert'] = time.strftime('%H:%M:%S')
                        _log('guard', cap)
                        cooldown = time.time() + 60
                        try:
                            import pathlib
                            d = pathlib.Path(__file__).with_name('recordings'); d.mkdir(exist_ok=True)
                            (d / time.strftime('guard_%Y%m%d_%H%M%S.jpg')).write_bytes(jpg)
                        except Exception: pass
        prev = jpg
        time.sleep(1.0)
    _state['guard_note'] = _state['guard_note'] if not _state['guard'] else 'off'

def guard(on):
    with _lock:
        if on and not _state['guard']:
            _state['follow'] = False
            _state['guard'] = True
            threading.Thread(target=_guard_loop, daemon=True).start()
            _log('guard', 'guard mode ON')
        elif not on and _state['guard']:
            _state['guard'] = False; _state['guard_note'] = 'off'
            _log('guard', 'guard mode OFF')
    return status()

# ---------------- FOLLOW ----------------
_turn_sign = [1]       # learned: +1 means 'person on the left of the image -> turn_left'

def _follow_loop():
    import vision
    _post('/action/stand'); time.sleep(1.2); _post('/head', yaw=0, roll=0, pitch=18)
    lost = 0; last_cx = 0.5; started = time.time(); last_turn = None
    _state['follow_note'] = 'looking for you'
    while _state['follow']:
        if time.time() - started > 600:                      # 10 min safety limit
            _state['follow_note'] = 'stopped after 10 min'; break
        jpg = _snap()
        if not jpg: time.sleep(0.5); continue
        people = vision.detect(jpg, only={'person'}, conf=0.4)
        if not people:
            lost += 1
            if lost == 3:
                _post('/move/stop')
            if 3 <= lost <= 12:                               # turn slowly toward where we last saw them
                d = 'turn_left' if (last_cx < 0.5) == (_turn_sign[0] > 0) else 'turn_right'
                _post(f'/move/{d}', ms=500, speed=80)
                _state['follow_note'] = 'lost you - searching'
            if lost > 12:
                _post('/move/stop'); _state['follow_note'] = 'lost you - stopped'
                _say('Anna, nuvvu kanipinchatledu. Follow aapesanu.')
                break
            time.sleep(0.4); continue
        lost = 0
        p = people[0]; cx = p['cx']; hfrac = p['box'][3] / 360.0
        try:
            import cv2, numpy as np
            hfrac = p['box'][3] / cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_GRAYSCALE).shape[0]
        except Exception: pass
        # learn turn direction: after a turn, the person should move toward the centre
        if last_turn and abs(cx - 0.5) > abs(last_cx - 0.5) + 0.08 and abs(last_cx - 0.5) > 0.15:
            _turn_sign[0] *= -1; print('[follow] flipped turn direction', flush=True)
        last_turn = None
        err = cx - 0.5
        if abs(err) > 0.17:
            d = 'turn_left' if (err < 0) == (_turn_sign[0] > 0) else 'turn_right'
            _post(f'/move/{d}', ms=450, speed=90); last_turn = d
            _state['follow_note'] = 'turning to you'
        elif hfrac < 0.75:
            _post('/move/forward', ms=700, speed=98)
            _state['follow_note'] = 'following'
        else:
            _post('/move/stop'); _state['follow_note'] = 'close to you - waiting'
        last_cx = cx
        time.sleep(0.35)
    _post('/move/stop')
    _state['follow'] = False

def follow(on):
    with _lock:
        if on and not _state['follow']:
            _state['guard'] = False
            _state['follow'] = True
            threading.Thread(target=_follow_loop, daemon=True).start()
            _log('follow', 'follow me ON')
        elif not on and _state['follow']:
            _state['follow'] = False; _state['follow_note'] = 'off'
            _post('/move/stop')
            _log('follow', 'follow me OFF')
    return status()
