#!/usr/bin/env python3
"""Chinnu voice loop (wake-word mode):
PiDog KWS wake -> ack -> mic -> STT -> brain (tools) -> TTS -> PiDog speaker -> one follow-up listen."""
import os, time, json, threading, requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
load_dotenv()
import voice, brain, robot

V = voice.V
brain.set_mode(script=V.get('script', 'telugu'), voice=True)
SECONDS = float(V.get('listen_seconds', 5))
FOLLOWUP = float(V.get('followup_seconds', 4))
SILENCE = float(V.get('silence_rms', 6))
FOLLOW_SILENCE = SILENCE + 2
STT_PROMPT = 'Chinnu, anna, Chintu, sit, stand, lie, wag tail, head tilt, forward, backward, stop, aagu'
STOP_WORDS = ('bye chinnu', 'chinnu bye', 'shutdown', 'exit voice', 'voice aapu')
ACK_WAV = '/tmp/chinnu_ack.wav'
HDR = voice.HDR; URL = voice.URL
DASH = 'http://127.0.0.1:8080/state'

def dash(mode=None, note=None, chat=None):
    d = {}
    if mode: d['mode'] = mode
    if note is not None: d['note'] = note
    if chat: d['chat'] = chat
    try: requests.post(DASH, json=d, timeout=1)
    except Exception: pass

def say_file(path):
    r = requests.post(f'{URL}/say', headers=HDR, data=open(path, 'rb').read(), timeout=90)
    return r.ok

def wait_wake(timeout=25):
    try:
        r = requests.get(f'{URL}/wake', headers=HDR, params={'timeout': timeout}, timeout=timeout + 10)
        return r.ok and r.json().get('woke', False)
    except Exception as e:
        print('[wake] error', e); time.sleep(3); return False

def hear(seconds, silence=None):
    wav, rms = voice.listen(seconds)
    if not wav or rms < (silence or SILENCE):
        return ''
    text = voice.stt(wav, prompt=STT_PROMPT)
    # gpt-4o-transcribe sometimes echoes the prompt on near-silence: drop those
    low = text.lower()
    words = [w.strip(' ,') for w in STT_PROMPT.lower().split(',')]
    hits = sum(1 for w in words if w and w in low)
    if hits >= 4 or low.strip(' .') == STT_PROMPT.lower():
        print('  (ignored prompt echo)', flush=True); return ''
    return text

chat_lock = threading.Lock()

# ---- instant spoken ack while the brain is still composing the reply (commands feel snappy) ----
QUICK_ACK = {'robot_action': 'Sare anna!', 'govee_plug': 'Sare anna!', 'power_strip': 'Sare anna!', 'home_light': 'Sare anna!', 'set_volume': 'Sare!', 'run_command': 'Sare anna!',
             'home_camera': 'Oka nimisham, chustha.', 'look': 'Chustha anna.', 'who_is_here': 'Chustha.', 'news': 'Oka nimisham.', 'weather': 'Chustha.'}
_ACK_FILES = {}
def _quick_ack_file(text):
    p = _ACK_FILES.get(text)
    if not p:
        p = f'/tmp/chinnu_qack_{abs(hash(text)) % 100000}.wav'
        if not os.path.exists(p):
            try: voice.tts(text, p)
            except Exception as e: print('[qack tts]', e, flush=True); return None
        _ACK_FILES[text] = p
    return p

_orig_run_tool = brain.run_tool
def _run_tool_with_ack(name, args):
    text = QUICK_ACK.get(name)
    if text and V.get('quick_ack', True):
        p = _quick_ack_file(text)
        if p: threading.Thread(target=say_file, args=(p,), daemon=True).start()
    return _orig_run_tool(name, args)
brain.run_tool = _run_tool_with_ack

def converse(text, speak=True):
    """One exchange; returns False if the user asked to stop the voice loop."""
    r = _converse(text, speak)
    return r is not False

def ask(text, speak=True):
    """Text entry point (dashboard): returns the reply string."""
    with chat_lock:
        r = _converse(text, speak)
    return r if isinstance(r, str) else ''

def _converse(text, speak=True):
    print(f'Chintu: {text}', flush=True); dash('thinking', chat={'who': 'Chintu', 'text': text})
    if any(w in text.lower() for w in STOP_WORDS):
        voice.say('Sare anna, bye bye!'); return False
    if speak and V.get('stream', True):
        reply = _speak_pipeline(text)
    else:
        try:
            reply = brain.chat(text)
        except Exception as e:
            print('[brain error] -> local LLM', e)
            try:
                import local_llm; reply = local_llm.chat(text)
            except Exception as e2:
                print('[local llm error]', e2); reply = 'Ayyo anna, brain lo chinna problem vachindi.'
        print(f'Chinnu: {reply}', flush=True)
        if reply and speak:
            try:
                path = voice.tts(reply)
            except Exception as e:
                print('[tts error]', e, flush=True); path = None
            dash('speaking', chat={'who': 'Chinnu', 'text': reply})
            if path:
                try: requests.post(f'{URL}/say', headers=HDR, data=open(path, 'rb').read(), timeout=60)
                except Exception as e: print('[say error]', e, flush=True)
        else:
            dash('thinking', chat={'who': 'Chinnu', 'text': reply})
    dash('idle')
    return reply

def _speak_pipeline(text):
    """Stream the brain reply sentence by sentence: TTS each sentence as soon as it is complete and play in order."""
    import queue
    q_tts = queue.Queue(); q_play = queue.Queue()
    shown = []
    n = [0]
    use_stream = bool(V.get('tts_stream', True))
    def tts_worker():
        while True:
            s = q_tts.get()
            if s is None: q_play.put(None); break
            n[0] += 1
            if use_stream:
                q_play.put(s)      # play_worker streams TTS -> robot directly
                continue
            try: q_play.put(voice.tts(s, f'/tmp/chinnu_tts_{n[0] % 4}.wav'))
            except Exception as e: print('[tts error]', e, flush=True)
    def play_worker():
        while True:
            p = q_play.get()
            if p is None: break
            try:
                if use_stream: voice.say_stream(p)
                else: requests.post(f'{URL}/say', headers=HDR, data=open(p, 'rb').read(), timeout=60)
            except Exception as e: print('[say error]', e, flush=True)
    t1 = threading.Thread(target=tts_worker, daemon=True); t2 = threading.Thread(target=play_worker, daemon=True)
    t1.start(); t2.start()
    def on_sentence(s):
        shown.append(s)
        dash('speaking', chat={'who': 'Chinnu', 'text': s})
        q_tts.put(s)
    try:
        reply = brain.chat_stream(text, on_sentence)
    except Exception as e:
        print('[brain error] -> local LLM', e, flush=True)
        try:
            import local_llm; reply = local_llm.chat(text)
        except Exception as e2:
            print('[local llm error]', e2, flush=True); reply = 'Ayyo anna, brain lo chinna problem vachindi.'
        on_sentence(reply)
    q_tts.put(None); t1.join(); t2.join()
    print(f'Chinnu: {reply}', flush=True)
    return reply

class _ChatHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0) or 0)
        try:
            d = json.loads(self.rfile.read(n) or b'{}')
        except Exception:
            d = {}
        text = (d.get('text') or '').strip()
        reply = ask(text, bool(d.get('speak', True))) if text else ''
        body = json.dumps({'ok': True, 'reply': reply}).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

def chat_server():
    HTTPServer(('127.0.0.1', 8081), _ChatHandler).serve_forever()

LOW_BAT_V = 6.9
_bat_warned = 0
def battery_thread():
    global _bat_warned
    time.sleep(30)
    while True:
        try:
            b = requests.get(f'{URL}/battery', headers=HDR, timeout=5).json()
            v = b.get('voltage')
            if v and v < LOW_BAT_V and time.time() - _bat_warned > 600:
                _bat_warned = time.time()
                with chat_lock:
                    voice.say(f'Anna, naa battery takkuva undi, {b.get("percent")} percent matrame undi. Charge pettu please!')
        except Exception as e:
            print('[battery]', e, flush=True)
        time.sleep(60)

_sched_done = {}
def scheduler_thread():
    """Run commands.yaml routines at their scheduled local time (checked every 20 s)."""
    import commands as custom_cmds
    while True:
        try:
            now = time.localtime()
            hhmm = time.strftime('%H:%M', now); today = time.strftime('%Y-%m-%d', now); dow = time.strftime('%a', now).lower()[:3]
            for name, sch in custom_cmds.scheduled().items():
                if sch['at'] != hhmm or _sched_done.get(name) == today:
                    continue
                if sch['days'] and dow not in sch['days']:
                    continue
                _sched_done[name] = today
                print(f'[schedule] {hhmm} -> {name}', flush=True)
                with chat_lock:
                    dash('thinking', note=f'schedule: {name}')
                    res = custom_cmds.run(name)
                    say_text = res.get('say') if isinstance(res, dict) else None
                    if say_text:
                        dash('speaking', chat={'who': 'Chinnu', 'text': say_text}); voice.say(say_text)
                    dash('idle')
        except Exception as e:
            print('[schedule] error', e, flush=True)
        time.sleep(20)

def reminder_thread():
    import extras
    time.sleep(15)
    while True:
        try:
            for r in extras.due_reminders():
                msg = f"Anna, reminder: {r['text']}"
                print('[reminder]', msg, flush=True)
                with chat_lock:
                    dash('speaking', chat={'who': 'Chinnu', 'text': msg})
                    try: voice.say(msg); time.sleep(1); voice.say(msg)
                    except Exception as e: print('[reminder] say failed', e, flush=True)
                    dash('idle')
                try: requests.post('http://127.0.0.1:8080/api/notify', json={'text': msg, 'kind': 'reminder'}, timeout=5)
                except Exception: pass
        except Exception as e:
            print('[reminder] error', e, flush=True)
        time.sleep(10)

def summary_thread():
    """Daily summary at config voice.summary_at (default 22:00): spoken + chat + phone."""
    done = None
    while True:
        try:
            at = str(V.get('summary_at', '22:00'))
            today = time.strftime('%Y-%m-%d')
            if time.strftime('%H:%M') == at and done != today:
                done = today
                import history
                text = history.summary_text()
                if text:
                    print('[summary]', text, flush=True)
                    with chat_lock:
                        dash('speaking', chat={'who': 'Chinnu', 'text': text})
                        try: voice.say(text)
                        except Exception as e: print('[summary] say failed', e, flush=True)
                        dash('idle')
                    try: requests.post('http://127.0.0.1:8080/api/notify', json={'text': 'Chinnu daily summary: ' + text, 'kind': 'summary'}, timeout=5)
                    except Exception: pass
        except Exception as e:
            print('[summary] error', e, flush=True)
        time.sleep(20)

IDLE = voice.CFG.get('idle', {}) or {}
last_wake = [0.0]
idle_moving = [False]
last_greet = {}

def _quiet_now():
    q = str(IDLE.get('quiet', '') or '')
    if '-' not in q: return False
    a, b = q.split('-', 1)
    now = time.strftime('%H:%M')
    return (a <= now or now < b) if a > b else (a <= now < b)

def _busy():
    return chat_lock.locked() or time.time() - last_wake[0] < 45

def idle_thread():
    """Random small behaviours when idle: head look-around, tilt, wag (never stretch - camera must stay level)."""
    import random
    time.sleep(30)
    while True:
        gap = random.uniform(float(IDLE.get('min_gap', 60)), float(IDLE.get('max_gap', 180)))
        time.sleep(gap)
        try:
            if not IDLE.get('enabled') or _quiet_now() or _busy(): continue
            pick = random.choice(['look', 'look', 'look', 'tilt_head', 'shake_head'])   # no wag when idle (Chintu: too much wagging)   # no stretch: it leaves the camera pointing at the floor
            if IDLE.get('track') and track_state['active'] and pick == 'look': pick = 'tilt_head'
            idle_moving[0] = True
            if pick == 'look':
                yaw = random.choice([-45, -25, 25, 45]); pitch = random.choice([-10, 0, 10])
                requests.post(robot.URL + '/head', headers=robot.HDR, params={'yaw': yaw, 'pitch': pitch, 'speed': 40}, timeout=5)
                time.sleep(random.uniform(1.5, 4))
                if _busy(): continue
                requests.post(robot.URL + '/head', headers=robot.HDR, params={'yaw': 0, 'pitch': 0, 'roll': 0, 'speed': 40}, timeout=5)
            else:
                robot.action(pick)
            print('[idle]', pick, flush=True)
        except Exception as e:
            print('[idle] error', e, flush=True)
        finally:
            idle_moving[0] = False

GREETS = ['Anna, vachava! Nenu ikkade vunna.', 'Hey Chintu anna! Miss ayyanu nuvvu.', 'Anna! Em chestunnav? Nenu ready.', 'Chintu anna vachesadu! Tail wag wag.']

def greet_thread():
    """Every face_interval s look for known faces; greet with cooldown."""
    import random
    time.sleep(40)
    while True:
        time.sleep(float(IDLE.get('face_interval', 20)))
        try:
            if not IDLE.get('greet') or _quiet_now() or _busy(): continue
            r = requests.get('http://127.0.0.1:8080/api/faces/identify', timeout=15).json()
            faces = r.get('faces') or []
            if not faces: continue
            now = time.time(); cd = float(IDLE.get('greet_cooldown', 600))
            known = [f['name'] for f in faces if f.get('name')]
            msg = None
            for n in known:
                if now - last_greet.get(n, 0) > cd:
                    last_greet[n] = now
                    msg = random.choice(GREETS) if n == 'Chintu' else f'Hai {n}! Nenu Chinnu.'
                    break
            if not msg and not known and IDLE.get('greet_unknown') and now - last_greet.get('?', 0) > cd:
                last_greet['?'] = now; msg = 'Evaru meeru? Nenu Chinnu, Chintu anna robo dog.'
            if not msg or _busy(): continue
            print('[greet]', known or 'unknown', msg, flush=True)
            with chat_lock:
                dash('speaking', chat={'who': 'Chinnu', 'text': msg})
                voice.say(msg)   # greeting without tail wag (Chintu: too much wagging)
                dash('idle')
            try: requests.post('http://127.0.0.1:8080/api/notify', json={'text': f'Chinnu saw {", ".join(known) or "someone"}', 'kind': 'greet'}, timeout=5)
            except Exception: pass
        except Exception as e:
            print('[greet] error', e, flush=True)

track_state = {'yaw': 0.0, 'pitch': 0.0, 'seen': 0.0, 'active': False}

def track_thread():
    """Keep the head pointed at the largest face (server-side detection on /snap.jpg)."""
    import faces
    time.sleep(35)
    hz = float(IDLE.get('track_hz', 3) or 3)
    ys = float(IDLE.get('track_yaw_sign', -1) or -1); ps = float(IDLE.get('track_pitch_sign', 1) or 1)
    while True:
        time.sleep(max(0.15, 1.0 / hz))
        try:
            if not IDLE.get('track') or _quiet_now() or idle_moving[0]:
                continue
            r = requests.get(robot.URL + '/snap.jpg', headers=robot.HDR, timeout=3)
            if not r.ok or len(r.content) < 500: continue
            img = faces._decode(r.content)
            H, W = img.shape[:2]
            fs = faces.detect(img)
            now = time.time()
            if len(fs) == 0:
                if track_state['active'] and now - track_state['seen'] > 6:
                    track_state.update(yaw=0.0, pitch=0.0, active=False)
                    requests.post(robot.URL + '/head', headers=robot.HDR, params={'yaw': 0, 'pitch': 0, 'roll': 0, 'speed': 30}, timeout=3)
                continue
            f = max(fs, key=lambda q: q[2] * q[3])
            dx = (f[0] + f[2] / 2) / W - 0.5; dy = (f[1] + f[3] / 2) / H - 0.5
            track_state['seen'] = now; track_state['active'] = True
            if abs(dx) < 0.06 and abs(dy) < 0.08: continue
            yaw = max(-80, min(80, track_state['yaw'] + ys * dx * 40))
            pitch = max(-35, min(28, track_state['pitch'] - ps * dy * 30))
            track_state.update(yaw=yaw, pitch=pitch)
            requests.post(robot.URL + '/head', headers=robot.HDR, params={'yaw': round(yaw, 1), 'pitch': round(pitch, 1), 'roll': 0, 'speed': 90}, timeout=3)
        except Exception as e:
            print('[track] error', e, flush=True); time.sleep(2)

def heartbeat_thread():
    import threading
    while True:
        try:
            requests.post(f'{URL}/heartbeat', headers=HDR, timeout=4)
        except Exception as e:
            print('[heartbeat] fail', e, flush=True)
        time.sleep(5)

_face = {}
def owner_check_async():
    import owner
    def run(): _face['owner'] = owner.face_check()
    _face.clear(); t = threading.Thread(target=run, daemon=True); t.start(); _face['t'] = t

def owner_mode():
    import owner
    t = _face.get('t')
    if t: t.join(timeout=4)
    return _face.get('owner', owner.is_owner()) if t else owner.is_owner()

def _my_model():
    try:
        import chinnu_llm, voice as _v; return chinnu_llm.mode() == 'chinnu' or _v.own_voice_on()
    except Exception: return False

def _rt_enabled():
    """Realtime voice unless saver mode (budget limit) is on."""
    return V.get('realtime', False) and not os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saver_mode.json')) and not _my_model()

def rt_turn(seconds, silence=None):
    """Realtime speech-to-speech turn. Returns 'silence' | 'stop' | 'ok' | 'fallback:<text>'."""
    wav, rms = voice.listen(seconds)
    if not wav or rms < (silence or SILENCE):
        return 'silence'
    import realtime
    is_owner = owner_mode()
    try:                                         # voice ID: decides per turn when confident
        import speaker, owner as _ow
        t0 = time.time(); vname, vscore = speaker.verify(wav)
        print(f'[voiceid] {vname} {vscore} ({time.time() - t0:.2f}s)', flush=True)
        if vname == 'Chintu':
            is_owner = True
            if vscore >= speaker.ADAPT: threading.Thread(target=speaker.adapt, args=('Chintu', wav), daemon=True).start()
            if not _ow.is_owner() or _ow.status()['seconds_left'] < 15 * 60: _ow.unlock(15, 'voice')
        elif 0 < vscore < speaker.LOW and speaker.last_secs >= 1.5:
            is_owner = False                     # clearly a different voice -> guest for this turn
    except Exception as e:
        print('[voiceid] error', e, flush=True)
    realtime.set_mode('owner' if is_owner else 'guest')
    who = 'Chintu' if is_owner else 'Guest'
    dash('thinking')
    def on_user(t):
        print(f'{who}: {t}', flush=True); dash('thinking', chat={'who': who, 'text': t})
    def on_reply(t):
        print(f'Chinnu: {t}', flush=True); dash('speaking', chat={'who': 'Chinnu', 'text': t})
    try:
        with chat_lock:
            user_text, reply = realtime.turn(wav, on_user, on_reply)
    except Exception as e:
        print('[realtime] failed, falling back:', e, flush=True)
        voice.credit_alert(e)
        if not is_owner:                       # classic brain has owner memory -> never for guests
            voice.say('Sorry, oka nimisham tarvata malli adagandi.'); return 'ok'
        try:
            text = voice.stt(wav, prompt=STT_PROMPT)
        except Exception: text = ''
        return 'fallback:' + (text or '')
    if any(w in (user_text or '').lower() for w in STOP_WORDS):
        return 'stop'
    dash('idle')
    return 'ok'

def main():
    threading.Thread(target=heartbeat_thread, daemon=True).start()
    threading.Thread(target=battery_thread, daemon=True).start()
    threading.Thread(target=scheduler_thread, daemon=True).start()
    threading.Thread(target=reminder_thread, daemon=True).start()
    threading.Thread(target=summary_thread, daemon=True).start()
    threading.Thread(target=idle_thread, daemon=True).start()
    threading.Thread(target=greet_thread, daemon=True).start()
    threading.Thread(target=track_thread, daemon=True).start()
    threading.Thread(target=chat_server, daemon=True).start()
    while True:
        try:
            print('Robot:', robot.health(), flush=True); break
        except Exception as e:
            print('[startup] robot not reachable yet:', e, flush=True); time.sleep(5)
    ack = str(V.get('ack', 'chime'))
    if ack == 'voice':
        if not os.path.exists(ACK_WAV): voice.tts('Cheppu anna!', ACK_WAV)
    elif ack == 'chime':
        import subprocess
        subprocess.run(['sox', '-n', '-r', '24000', '-c', '1', ACK_WAV, 'synth', '0.11', 'sine', '1046', 'fade', '0.01', '0.11', '0.04', 'vol', '0.5', ':', 'synth', '0.14', 'sine', '1568', 'fade', '0.01', '0.14', '0.06', 'vol', '0.5'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if _rt_enabled():
        try:
            import realtime; threading.Thread(target=realtime.warmup, daemon=True).start()
        except Exception as e: print('[realtime] import', e, flush=True)
    try: voice.say('Hai anna, nenu ready. Chinnu ani pilichi matladu.')
    except Exception as e: print('[startup] say failed (OpenAI credits/network?):', str(e)[:120], flush=True)
    while True:
        try:
            import music; music.resume_if_paused()   # conversation over -> continue the song
        except Exception as e: print('[music]', e, flush=True)
        if not wait_wake():
            continue
        last_wake[0] = time.time()
        print('[wake]', time.strftime('%H:%M:%S'), flush=True); dash('listening', note='')
        owner_check_async()
        try:
            import music
            if music.is_playing(): music.pause()
        except Exception as e: print('[music]', e, flush=True)
        if ack != 'none': say_file(ACK_WAV)
        if _rt_enabled():
            r = rt_turn(SECONDS)
            if r == 'silence':
                print('  (nothing heard)', flush=True); dash('idle'); continue
            if r == 'stop':
                voice.say('Sare anna, bye bye!'); break
            if r.startswith('fallback:'):
                text = r[9:]
                if len(text) < 2: dash('idle'); continue
                with chat_lock: ok = converse(text)
                if not ok: break
            while True:                                  # follow-up turns
                last_wake[0] = time.time()
                r = rt_turn(FOLLOWUP, FOLLOW_SILENCE)
                if r == 'silence': dash('idle'); break
                if r == 'stop': voice.say('Sare anna, bye bye!'); return
                if r.startswith('fallback:'):
                    text = r[9:]
                    if len(text) < 2: dash('idle'); break
                    with chat_lock: ok = converse(text)
                    if not ok: return
            continue
        text = hear(SECONDS)
        if not text or len(text) < 2:
            print('  (nothing heard)', flush=True); dash('idle'); continue
        with chat_lock:
            ok = converse(text)
        if not ok:
            break
        # follow-up turns without the wake word, until silence
        while True:
            last_wake[0] = time.time()
            text = hear(FOLLOWUP, FOLLOW_SILENCE)
            if not text or len(text) < 2:
                dash('idle'); break
            with chat_lock:
                ok = converse(text)
            if not ok:
                return

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nstopped')
