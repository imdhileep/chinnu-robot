v = open('voice_agent.py', encoding='utf-8').read()
if 'def rt_turn' not in v:
    # helper: listen -> realtime turn; returns True if something was said, 'stop' on stop words, False if silence
    old = "def main():\n"
    new = '''def rt_turn(seconds, silence=None):
    """Realtime speech-to-speech turn. Returns 'silence' | 'stop' | 'ok' | 'fallback:<text>'."""
    wav, rms = voice.listen(seconds)
    if not wav or rms < (silence or SILENCE):
        return 'silence'
    import realtime
    dash('thinking')
    def on_user(t):
        print(f'Chintu: {t}', flush=True); dash('thinking', chat={'who': 'Chintu', 'text': t})
    def on_reply(t):
        print(f'Chinnu: {t}', flush=True); dash('speaking', chat={'who': 'Chinnu', 'text': t})
    try:
        with chat_lock:
            user_text, reply = realtime.turn(wav, on_user, on_reply)
    except Exception as e:
        print('[realtime] failed, falling back:', e, flush=True)
        try:
            text = voice.stt(wav, prompt=STT_PROMPT)
        except Exception: text = ''
        return 'fallback:' + (text or '')
    if any(w in (user_text or '').lower() for w in STOP_WORDS):
        return 'stop'
    dash('idle')
    return 'ok'

def main():
'''
    assert old in v; v = v.replace(old, new, 1)
    old2 = '''        if ack != 'none': say_file(ACK_WAV)
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
'''
    new2 = '''        if ack != 'none': say_file(ACK_WAV)
        if V.get('realtime', False):
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
'''
    assert old2 in v; v = v.replace(old2, new2, 1)
    # warm up the realtime socket at startup
    v = v.replace("    voice.say('Hai anna, nenu ready. Chinnu ani pilichi matladu.')\n",
                  "    if V.get('realtime', False):\n        try:\n            import realtime; threading.Thread(target=realtime.warmup, daemon=True).start()\n        except Exception as e: print('[realtime] import', e, flush=True)\n    voice.say('Hai anna, nenu ready. Chinnu ani pilichi matladu.')\n", 1)
    open('voice_agent.py', 'w', encoding='utf-8').write(v); print('voice_agent ok')

c = open('config.yaml', encoding='utf-8-sig').read()
if 'realtime:' not in c:
    c = c.replace("  ack: chime", "  realtime: true        # OpenAI Realtime speech-to-speech (fast); false = STT -> GPT -> TTS\n  realtime_model: gpt-realtime\n  realtime_voice: marin\n  ack: chime", 1)
    open('config.yaml', 'w', encoding='utf-8').write(c); print('config ok')
