import re
# ---------------- brain.py: streaming chat with sentence callback ----------------
b = open('brain.py', encoding='utf-8').read()
if 'def chat_stream' not in b:
    b = b.replace('def _trim():', '''_SENT_END = re.compile(r'([.!?।]+|\\n)')

def _split_ready(buf, min_len=14):
    """Return (ready_sentence, rest) when buf holds a complete sentence of at least min_len chars."""
    m = None
    for mm in _SENT_END.finditer(buf):
        if mm.end() >= min_len:
            m = mm; break
    if not m: return None, buf
    return buf[:m.end()].strip(), buf[m.end():]

def chat_stream(user_text: str, on_sentence):
    """Like chat() but streams: calls on_sentence(text) for each completed sentence as it arrives.
    Tool calls are collected from the stream, executed, and the loop continues. Returns the full reply."""
    history[0] = {"role": "system", "content": SYSTEM + extras.memory_block()}
    history.append({"role": "user", "content": user_text})
    full = ""
    for _ in range(5):
        stream = client.chat.completions.create(model=CFG["model"], messages=history, tools=TOOLS, stream=True)
        buf = ""; content = ""; calls = {}
        for chunk in stream:
            if not chunk.choices: continue
            d = chunk.choices[0].delta
            if d.content:
                content += d.content; buf += d.content
                s, buf = _split_ready(buf)
                if s:
                    on_sentence(s); full += (" " if full else "") + s
            for tc in (d.tool_calls or []):
                c = calls.setdefault(tc.index, {"id": tc.id or "", "name": "", "args": ""})
                if tc.id: c["id"] = tc.id
                if tc.function and tc.function.name: c["name"] += tc.function.name
                if tc.function and tc.function.arguments: c["args"] += tc.function.arguments
        if buf.strip():
            on_sentence(buf.strip()); full += (" " if full else "") + buf.strip()
        if not calls:
            history.append({"role": "assistant", "content": content})
            _trim()
            return full
        tool_calls = [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["args"] or "{}"}} for _, c in sorted(calls.items())]
        history.append({"role": "assistant", "content": content or None, "tool_calls": tool_calls})
        for tc in tool_calls:
            try: args = json.loads(tc["function"]["arguments"] or "{}")
            except Exception: args = {}
            result = run_tool(tc["function"]["name"], args)
            print(f"  [tool] {tc['function']['name']}({args}) -> {result}")
            history.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(result)})
    _trim()
    return full or "Sorry anna, konchem confuse ayyanu."

def _trim():''', 1)
    if '\nimport re' not in b and not b.startswith('import re'):
        b = b.replace('import json', 'import json, re', 1) if 'import json' in b else 'import re\n' + b
    open('brain.py', 'w', encoding='utf-8').write(b); print('brain ok')

# ---------------- voice_agent.py: pipelined TTS/play + chime ack ----------------
v = open('voice_agent.py', encoding='utf-8').read()
if 'def _speak_pipeline' not in v:
    old = '''    try:
        reply = brain.chat(text)
    except Exception as e:
        print('[brain error]', e); reply = 'Ayyo anna, brain lo chinna problem vachindi.'
    print(f'Chinnu: {reply}', flush=True)
    if reply and speak:
        try:
            path = voice.tts(reply)          # generate audio first so text + voice land together
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
'''
    new = '''    if speak and V.get('stream', True):
        reply = _speak_pipeline(text)
    else:
        try:
            reply = brain.chat(text)
        except Exception as e:
            print('[brain error]', e); reply = 'Ayyo anna, brain lo chinna problem vachindi.'
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
    def tts_worker():
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
    t1 = threading.Thread(target=tts_worker, daemon=True); t2 = threading.Thread(target=play_worker, daemon=True)
    t1.start(); t2.start()
    def on_sentence(s):
        shown.append(s)
        dash('speaking', chat={'who': 'Chinnu', 'text': s})
        q_tts.put(s)
    try:
        reply = brain.chat_stream(text, on_sentence)
    except Exception as e:
        print('[brain error]', e, flush=True); reply = 'Ayyo anna, brain lo chinna problem vachindi.'
        on_sentence(reply)
    q_tts.put(None); t1.join(); t2.join()
    print(f'Chinnu: {reply}', flush=True)
    return reply
'''
    assert old in v, 'converse block not found'
    v = v.replace(old, new, 1)
    # chime ack (config voice.ack: chime | voice | none)
    v = v.replace('''    if not os.path.exists(ACK_WAV):
        voice.tts('Cheppu anna!', ACK_WAV)
''', '''    ack = str(V.get('ack', 'chime'))
    if ack == 'voice':
        if not os.path.exists(ACK_WAV): voice.tts('Cheppu anna!', ACK_WAV)
    elif ack == 'chime':
        import subprocess
        subprocess.run(['sox', '-n', '-r', '24000', '-c', '1', ACK_WAV, 'synth', '0.11', 'sine', '1046', 'fade', '0.01', '0.11', '0.04', 'vol', '0.5', ':', 'synth', '0.14', 'sine', '1568', 'fade', '0.01', '0.14', '0.06', 'vol', '0.5'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
''', 1)
    v = v.replace("        say_file(ACK_WAV)\n        text = hear(SECONDS)", "        if ack != 'none': say_file(ACK_WAV)\n        text = hear(SECONDS)", 1)
    open('voice_agent.py', 'w', encoding='utf-8').write(v); print('voice_agent ok')

c = open('config.yaml', encoding='utf-8-sig').read()
if 'ack:' not in c:
    c = c.replace("  summary_at: '22:00'", "  summary_at: '22:00'\n  ack: chime          # chime | voice | none  (sound after the wake word)\n  stream: true        # speak sentence-by-sentence while the brain is still writing", 1)
    open('config.yaml', 'w', encoding='utf-8').write(c); print('config ok')
