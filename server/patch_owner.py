import re, shutil, time
ts = time.strftime('%H%M%S')
def patch(fn, pairs):
    s = open(fn, encoding='utf-8').read()
    shutil.copy(fn, f'{fn}.bak_owner{ts}')
    for a, b in pairs:
        assert s.count(a) == 1, (fn, a[:60], s.count(a))
        s = s.replace(a, b)
    open(fn, 'w', encoding='utf-8').write(s)
    print('patched', fn)

# ---------- realtime.py: separate owner / guest sessions ----------
patch('realtime.py', [
("import brain, voice, extras\n",
 "import brain, voice, extras, owner\n_mode = 'owner'          # mode of the current websocket session\n"),
("def _tools():\n    return [",
 "def _tools():\n    allowed = None if _mode == 'owner' else owner.GUEST_TOOLS\n    return ["),
("for t in brain.TOOLS]",
 "for t in brain.TOOLS if allowed is None or t['function']['name'] in allowed]"),
("def _instructions():\n    return (",
 "def _instructions():\n    if _mode != 'owner':\n        return owner.GUEST_PROMPT\n    return ("),
("'Do not announce that you are calling a tool; just call it, then answer.')",
 "'Do not announce that you are calling a tool; just call it, then answer. '\n"
 "            'You are in OWNER mode: the speaker was verified as Chintu (face or phone unlock).')"),
("def _turn(wav_bytes, on_user=None, on_reply=None):\n    with _lock:\n        ws = _get_ws()\n",
 "def set_mode(mode):\n    \"\"\"Switch owner/guest. A switch always starts a FRESH session so no earlier conversation leaks.\"\"\"\n"
 "    global _mode, _ws\n    if mode == _mode: return\n    with _lock:\n        _mode = mode\n"
 "        if _ws is not None:\n            try: _ws.close()\n            except Exception: pass\n            _ws = None\n"
 "    print(f'[realtime] mode -> {mode} (new session)', flush=True)\n\n"
 "def _turn(wav_bytes, on_user=None, on_reply=None):\n    with _lock:\n        ws = _get_ws()\n"),
("                        result = brain.run_tool(name, a)\n",
 "                        if _mode != 'owner' and name not in owner.GUEST_TOOLS:\n"
 "                            result = {'ok': False, 'error': 'not allowed for guests'}\n"
 "                        else:\n                            result = brain.run_tool(name, a)\n"),
("            if user_text: brain.history.append",
 "            if _mode == 'owner' and user_text: brain.history.append"),
("            if reply_text: brain.history.append",
 "            if _mode == 'owner' and reply_text: brain.history.append"),
])

# ---------- voice_agent.py: verify on every wake ----------
patch('voice_agent.py', [
("def rt_turn(seconds, silence=None):\n    \"\"\"Realtime speech-to-speech turn. Returns 'silence' | 'stop' | 'ok' | 'fallback:<text>'.\"\"\"\n    wav, rms = voice.listen(seconds)\n",
 "_face = {}\ndef owner_check_async():\n    import owner\n    def run(): _face['owner'] = owner.face_check()\n"
 "    _face.clear(); t = threading.Thread(target=run, daemon=True); t.start(); _face['t'] = t\n\n"
 "def owner_mode():\n    import owner\n    t = _face.get('t')\n    if t: t.join(timeout=4)\n"
 "    return _face.get('owner', owner.is_owner()) if t else owner.is_owner()\n\n"
 "def rt_turn(seconds, silence=None):\n    \"\"\"Realtime speech-to-speech turn. Returns 'silence' | 'stop' | 'ok' | 'fallback:<text>'.\"\"\"\n    wav, rms = voice.listen(seconds)\n"),
("    import realtime\n    dash('thinking')\n    def on_user(t):\n        print(f'Chintu: {t}'",
 "    import realtime\n    is_owner = owner_mode()\n    realtime.set_mode('owner' if is_owner else 'guest')\n    who = 'Chintu' if is_owner else 'Guest'\n"
 "    dash('thinking')\n    def on_user(t):\n        print(f'{who}: {t}'"),
("dash('thinking', chat={'who': 'Chintu', 'text': t})\n    def on_reply",
 "dash('thinking', chat={'who': who, 'text': t})\n    def on_reply"),
("        print('[realtime] failed, falling back:', e, flush=True)\n",
 "        print('[realtime] failed, falling back:', e, flush=True)\n"
 "        if not is_owner:                       # classic brain has owner memory -> never for guests\n"
 "            voice.say('Sorry, oka nimisham tarvata malli adagandi.'); return 'ok'\n"),
("        last_wake[0] = time.time()\n        print('[wake]', time.strftime('%H:%M:%S'), flush=True); dash('listening', note='')\n",
 "        last_wake[0] = time.time()\n        print('[wake]', time.strftime('%H:%M:%S'), flush=True); dash('listening', note='')\n        owner_check_async()\n"),
])
