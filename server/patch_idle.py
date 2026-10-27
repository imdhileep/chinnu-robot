import re
# ---------- config.yaml ----------
c = open('config.yaml', encoding='utf-8-sig').read()
if '\nidle:' not in c:
    c = c.rstrip('\n') + '''
idle:
  enabled: false          # random head tilt / look around / stretch when nothing is happening
  min_gap: 60             # seconds between idle actions (random between min and max)
  max_gap: 180
  quiet: "23:00-07:00"    # no idle actions / greetings in this window
  greet: true             # say hi when a known face appears (face recognition)
  greet_cooldown: 600     # seconds before greeting the same person again
  greet_unknown: false    # ask "evaru meeru?" for unknown faces
  face_interval: 20       # seconds between camera face checks
'''
    open('config.yaml', 'w', encoding='utf-8').write(c); print('config ok')

# ---------- voice_agent.py ----------
v = open('voice_agent.py', encoding='utf-8').read()
if 'def idle_thread' not in v:
    v = v.replace('def heartbeat_thread():', '''IDLE = voice.CFG.get('idle', {}) or {}
last_wake = [0.0]
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
    """Random small behaviours when idle: head look-around, tilt, stretch, wag."""
    import random
    time.sleep(30)
    while True:
        gap = random.uniform(float(IDLE.get('min_gap', 60)), float(IDLE.get('max_gap', 180)))
        time.sleep(gap)
        try:
            if not IDLE.get('enabled') or _quiet_now() or _busy(): continue
            pick = random.choice(['look', 'look', 'tilt_head', 'shake_head', 'stretch', 'wag_tail'])
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
                try: robot.action('wag_tail')
                except Exception: pass
                voice.say(msg)
                dash('idle')
            try: requests.post('http://127.0.0.1:8080/api/notify', json={'text': f'Chinnu saw {", ".join(known) or "someone"}', 'kind': 'greet'}, timeout=5)
            except Exception: pass
        except Exception as e:
            print('[greet] error', e, flush=True)

def heartbeat_thread():''', 1)
    v = v.replace("    threading.Thread(target=summary_thread, daemon=True).start()\n",
                  "    threading.Thread(target=summary_thread, daemon=True).start()\n    threading.Thread(target=idle_thread, daemon=True).start()\n    threading.Thread(target=greet_thread, daemon=True).start()\n", 1)
    v = v.replace("        print('[wake]', time.strftime('%H:%M:%S'), flush=True); dash('listening', note='')",
                  "        last_wake[0] = time.time()\n        print('[wake]', time.strftime('%H:%M:%S'), flush=True); dash('listening', note='')", 1)
    # keep last_wake fresh during follow-up turns
    v = v.replace("            text = hear(FOLLOWUP, FOLLOW_SILENCE)\n", "            last_wake[0] = time.time()\n            text = hear(FOLLOWUP, FOLLOW_SILENCE)\n", 1)
    open('voice_agent.py', 'w', encoding='utf-8').write(v); print('voice ok')

# ---------- settings: Idle card + API ----------
st = open('settings.py', encoding='utf-8').read()
if '/api/settings/idle' not in st:
    st = st.replace("@router.post('/api/settings/voice')", '''@router.post('/api/settings/idle')
async def save_idle(req: Request):
    d = await req.json()
    cfg = yaml.safe_load(open(CFG_FILE, encoding='utf-8-sig')) or {}
    i = cfg.setdefault('idle', {})
    for k in ('enabled', 'greet', 'greet_unknown'):
        if k in d: i[k] = bool(d[k])
    for k in ('min_gap', 'max_gap', 'greet_cooldown', 'face_interval'):
        if d.get(k) not in (None, ''): i[k] = float(d[k])
    if d.get('quiet') is not None: i['quiet'] = str(d['quiet'])
    open(CFG_FILE, 'w', encoding='utf-8').write(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))
    subprocess.Popen(['sudo', 'systemctl', 'restart', 'chinnu-voice'])
    return {'ok': True, 'idle': i, 'note': 'voice service restarting'}

@router.post('/api/settings/voice')''', 1)
    st = st.replace("            'memory': extras.facts(),", "            'idle': cfg.get('idle', {}), 'memory': extras.facts(),", 1)
    st = st.replace('<div class="card"><h3>Voice</h3>', '''<div class="card"><h3>Idle behaviours &amp; greeting</h3><div class="kv" id="idle"></div><div class="row"><button class="ok" onclick="saveIdle()">Save &amp; restart voice</button></div></div>
<div class="card"><h3>Voice</h3>''', 1)
    st = st.replace("const v=S.voice;", '''const I=S.idle||{};$('idle').innerHTML=[['enabled','idle actions (head look / tilt / stretch)','chk'],['greet','greet known faces','chk'],['greet_unknown','ask unknown faces','chk'],['min_gap','min gap (s)'],['max_gap','max gap (s)'],['quiet','quiet hours (HH:MM-HH:MM)'],['greet_cooldown','greet cooldown (s)'],['face_interval','face check every (s)']].map(([k,l,t])=>'<span>'+l+'</span>'+(t==='chk'?'<input type="checkbox" id="i_'+k+'" '+(I[k]?'checked':'')+' style="width:22px;height:22px">':'<input id="i_'+k+'" value="'+(I[k]??'')+'">')).join('');
const v=S.voice;''', 1)
    st = st.replace("async function saveVoice(){", '''async function saveIdle(){const b={};['enabled','greet','greet_unknown'].forEach(k=>b[k]=$('i_'+k).checked);['min_gap','max_gap','quiet','greet_cooldown','face_interval'].forEach(k=>b[k]=$('i_'+k).value);const r=await post('/api/settings/idle',b);alert(r.ok?'saved, voice restarting':JSON.stringify(r))}
async function saveVoice(){''', 1)
    open('settings.py', 'w', encoding='utf-8').write(st); print('settings ok')
