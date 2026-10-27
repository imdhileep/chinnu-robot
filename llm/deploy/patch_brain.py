"""Wire Chinnu-LLM into the agent: brain.chat/chat_stream, offline fallback, realtime off in my-model mode,
dashboard endpoints + app toggle + feature check."""
import re
# ---- brain.py ----
p = 'brain.py'; s = open(p).read()
hook = '''    try:
        import chinnu_llm
        if chinnu_llm.mode() == 'chinnu':
            _r = chinnu_llm.chat(user_text)
            %s
            return _r
    except Exception as _e:
        print('[chinnu-llm] failed, using GPT:', _e, flush=True)
'''
a = 'def chat(user_text: str) -> str:\n'
if 'chinnu_llm' not in s:
    s = s.replace(a, a + hook % '', 1)
    b = 'def chat_stream(user_text: str, on_sentence):\n    """Like chat() but streams: calls on_sentence(text) for each completed sentence as it arrives.\n    Tool calls are collected from the stream, executed, and the loop continues. Returns the full reply."""\n'
    assert s.count(b) == 1
    s = s.replace(b, b + hook % 'on_sentence(_r)', 1)
open(p, 'w').write(s)

# ---- local_llm.py: offline fallback uses Chinnu-LLM when it is installed ----
p = 'local_llm.py'; s = open(p).read()
a = 'def chat(text):\n'
if 'chinnu_llm' not in s:
    s = s.replace(a, a + '''    try:
        import chinnu_llm
        if chinnu_llm.available(): return chinnu_llm.chat(text)
    except Exception as e:
        print('[local] chinnu-llm failed', e, flush=True)
''', 1)
open(p, 'w').write(s)

# ---- voice_agent.py: no realtime (OpenAI speech-to-speech) in my-model mode ----
p = 'voice_agent.py'; s = open(p).read()
old = "    return V.get('realtime', False) and not os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saver_mode.json'))"
new = old + " and not _my_model()"
if '_my_model' not in s:
    assert s.count(old) == 1
    s = s.replace(old, new)
    s = s.replace('def _rt_enabled():', '''def _my_model():
    try:
        import chinnu_llm; return chinnu_llm.mode() == 'chinnu'
    except Exception: return False

def _rt_enabled():''', 1)
open(p, 'w').write(s)

# ---- dashboard.py: endpoints ----
p = 'dashboard.py'; s = open(p).read()
if '/api/brain_mode' not in s:
    s += '''

@app.get('/api/brain_mode')
def api_brain_mode():
    import chinnu_llm; return chinnu_llm.status()

@app.post('/api/brain_mode/{act}')
def api_brain_mode_set(act: str):
    import chinnu_llm
    if act == 'on' and not chinnu_llm.available():
        return JSONResponse({'ok': False, 'error': 'chinnu:3b model not installed in Ollama'}, status_code=400)
    chinnu_llm.set_mode('chinnu' if act == 'on' else 'gpt')
    try:
        import history; history.log('alert', 'Brain: ' + ('Chinnu-LLM (my model)' if act == 'on' else 'GPT-4.1'))
    except Exception: pass
    return chinnu_llm.status()
'''
open(p, 'w').write(s)

# ---- uptime.py: feature + mode ----
p = 'uptime.py'; s = open(p).read()
if "'chinnu_llm'" not in s:
    s = s.replace("    ('ai', 'Ollama local brain', 'ollama', None, 'ollama'),",
                  "    ('ai', 'Ollama local brain', 'ollama', None, 'ollama'),\n    ('ai', 'Chinnu-LLM (my own model)', 'chinnu_llm', None, None),")
    s = s.replace("            elif kind == 'govee':",
                  "            elif kind == 'chinnu_llm':\n                import chinnu_llm; st = chinnu_llm.status()\n                out[k] = (st['available'], ('ACTIVE brain' if st['mode'] == 'chinnu' else 'installed, GPT is active') if st['available'] else 'not installed')\n            elif kind == 'govee':")
    s = s.replace("    try: import ops; m['saver'] = ops.saver_on()",
                  "    try: import chinnu_llm; m['mymodel'] = chinnu_llm.mode() == 'chinnu'\n    except Exception: pass\n    try: import ops; m['saver'] = ops.saver_on()")
open(p, 'w').write(s)

# ---- mobile.py: toggle in Modes ----
p = 'mobile.py'; s = open(p, encoding='utf-8').read()
a = "tg('saver',m.saver,'&#128176; Saver mode','cheaper models, no realtime voice')+"
if 'mymodel' not in s:
    assert s.count(a) == 1
    s = s.replace(a, a + "tg('mymodel',m.mymodel,'&#129504; My model (Chinnu-LLM)','your own AI on the server, no GPT bill')+")
    b = "saver:'/api/ops/saver/'+a,"
    s = s.replace(b, b + "mymodel:'/api/brain_mode/'+a,")
open(p, 'w', encoding='utf-8').write(s)
print('patched')
