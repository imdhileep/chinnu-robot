v = open('voice.py', encoding='utf-8').read()
if 'def say_stream' not in v:
    v = v.replace("def say(text):", '''def say_stream(text):
    """Stream TTS PCM (24 kHz s16 mono) straight to the robot's /say/stream so playback starts after ~0.4 s.
    Pitch shift (child voice) is done on the robot with sox in streaming mode. Falls back to say() on error."""
    pitch = int(V.get('child_pitch', 600)) if V.get('child_voice', True) else 0
    def gen():
        with client.audio.speech.with_streaming_response.create(
                model=V.get('tts_model', 'gpt-4o-mini-tts'), voice=V.get('voice', 'echo'), input=text,
                response_format='pcm', instructions=CHILD_INSTRUCTIONS) as resp:
            for chunk in resp.iter_bytes(chunk_size=4096):
                if chunk: yield chunk
    try:
        r = requests.post(f'{URL}/say/stream', headers={**HDR, 'Content-Type': 'application/octet-stream'},
                          params={'rate': 24000, 'pitch': pitch}, data=gen(), timeout=90)
        if r.ok: return r.json()
        print('[say_stream] robot said', r.status_code, r.text[:80], '- falling back')
    except Exception as e:
        print('[say_stream] error', e, '- falling back')
    return say(text)

def say(text):''', 1)
    open('voice.py', 'w', encoding='utf-8').write(v); print('voice.py ok')

a = open('voice_agent.py', encoding='utf-8').read()
if 'say_stream' not in a:
    old = '''    def tts_worker():
        while True:
            s = q_tts.get()
            if s is None: q_play.put(None); break
            n[0] += 1
            try: q_play.put(voice.tts(s, f'/tmp/chinnu_tts_{n[0] % 4}.wav'))
            except Exception as e: print('[tts error]', e, flush=True)
    def play_worker():
        while True:
            p = q_play.get()
            if p is None: break
            try: requests.post(f'{URL}/say', headers=HDR, data=open(p, 'rb').read(), timeout=60)
            except Exception as e: print('[say error]', e, flush=True)
'''
    new = '''    use_stream = bool(V.get('tts_stream', True))
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
'''
    assert old in a; a = a.replace(old, new, 1)
    open('voice_agent.py', 'w', encoding='utf-8').write(a); print('voice_agent ok')
