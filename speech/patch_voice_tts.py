"""Chinnu's own voice: when own_voice.json says on and the Mac speech server is up, speak with the local voice model;
otherwise the OpenAI voice exactly as before."""
p = 'voice.py'; s = open(p).read()
helper = '''
OWN_VOICE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'own_voice.json')
tts_stats = {'own': 0, 'openai': 0, 'last': None}

def own_voice_on():
    try:
        import json as _json; return bool(_json.load(open(OWN_VOICE_FILE)).get('on'))
    except Exception: return False

def set_own_voice(on):
    import json as _json; _json.dump({'on': bool(on)}, open(OWN_VOICE_FILE, 'w')); return own_voice_on()

def _tts_own(text):
    """WAV bytes in Chinnu's own voice from the Mac, or None."""
    if not own_voice_on(): return None
    try:
        r = requests.post(f'{LOCAL_SPEECH}/tts', json={'text': text}, timeout=20)
        if r.ok and len(r.content) > 1000:
            tts_stats['own'] += 1; tts_stats['last'] = 'own'; return r.content
    except Exception: pass
    return None

'''
if '_tts_own' not in s:
    s = s.replace("def tts(text, path='/tmp/chinnu_tts.wav'):\n", helper + "def tts(text, path='/tmp/chinnu_tts.wav'):\n"
                  "    own = _tts_own(text)\n"
                  "    if own:\n"
                  "        open(path, 'wb').write(own); return path\n"
                  "    tts_stats['openai'] += 1; tts_stats['last'] = 'openai'\n", 1)
    s = s.replace('def say_stream(text):\n    """', 'def say_stream(text):\n    if own_voice_on():\n        return say(text)            # own voice: whole sentence WAV via /say\n    """', 1)
open(p, 'w').write(s)

# LOCAL_SPEECH must be defined before the helper is used (it is defined in the STT patch further down) -> fine at call time.
p = 'dashboard.py'; s = open(p).read()
if '/api/own_voice' not in s:
    s += '''

@app.get('/api/own_voice')
def api_own_voice():
    import voice
    try: mac = requests.get(voice.LOCAL_SPEECH + '/health', timeout=2).json()
    except Exception: mac = {}
    return {'on': voice.own_voice_on(), 'ready': bool(mac.get('tts_ready')), 'stt_on_mac': bool(mac.get('stt_ready'))}

@app.post('/api/own_voice/{act}')
def api_own_voice_set(act: str):
    import voice; voice.set_own_voice(act == 'on'); return api_own_voice()
'''
open(p, 'w').write(s)

p = 'uptime.py'; s = open(p).read()
if "'ownvoice'" not in s:
    s = s.replace("    try: import ops; m['saver'] = ops.saver_on()",
                  "    try: import voice; m['ownvoice'] = voice.own_voice_on()\n    except Exception: pass\n    try: import ops; m['saver'] = ops.saver_on()", 1)
open(p, 'w').write(s)

p = 'mobile.py'; s = open(p, encoding='utf-8').read()
a = "tg('mymodel',m.mymodel,'&#129504; My model (Chinnu-LLM)','your own AI on the server, no GPT bill')+"
if 'ownvoice' not in s and a in s:
    s = s.replace(a, a + "tg('ownvoice',m.ownvoice,'&#128483; Chinnu&#39;s own voice','offline voice (needs the Mac on)')+")
    s = s.replace("mymodel:'/api/brain_mode/'+a,", "mymodel:'/api/brain_mode/'+a,ownvoice:'/api/own_voice/'+a,")
open(p, 'w', encoding='utf-8').write(s)
print('patched')
