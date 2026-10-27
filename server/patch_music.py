import shutil, time
ts = time.strftime('%H%M%S')
fn = 'brain.py'; s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_music' + ts)
if '"play_music"' not in s:
    tools = '''  {"type": "function", "function": {
    "name": "play_music",
    "description": "Play a song on Chinnu's speaker. Searches Chintu's own music folder first (his own songs), else YouTube. query = song name + movie/artist, e.g. 'Naatu Naatu RRR', 'Amma song'. Use for 'paata pettu', 'song play cheyi', 'play ...'.",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
  {"type": "function", "function": {
    "name": "stop_music",
    "description": "Stop the song that is playing (also: 'paata aapu', 'stop song'). Use music_status for 'what song is this'.",
    "parameters": {"type": "object", "properties": {"status_only": {"type": "boolean"}}}}},
'''
    anchor = '  {"type": "function", "function": {\n    "name": "who_is_here"'
    assert s.count(anchor) == 1
    s = s.replace(anchor, tools + anchor)
    a2 = '        if name == "who_is_here":\n'
    s = s.replace(a2, '''        if name == "play_music":
            import music; return music.play(args.get("query", ""))
        if name == "stop_music":
            import music
            return music.status() if args.get("status_only") else music.stop()
''' + a2, 1)
    s = s.replace("ROBOT BODY:", "MUSIC: you CAN play songs now - use play_music (never say you cannot play songs); stop_music to stop. ROBOT BODY:", 1)
    open(fn, 'w', encoding='utf-8').write(s); print('brain ok')

# voice agent: saying the wake word stops the music so Chintu can talk
fn = 'voice_agent.py'; v = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_music' + ts)
a = "        owner_check_async()\n"
if 'music.stop' not in v:
    assert v.count(a) == 1
    v = v.replace(a, a + "        try:\n            import music\n            if music.is_playing(): music.stop()\n        except Exception as e: print('[music]', e, flush=True)\n")
    open(fn, 'w', encoding='utf-8').write(v); print('voice_agent ok')

# guests may play music too (nothing private)
o = open('owner.py', encoding='utf-8').read()
if "'play_music'" not in o:
    o = o.replace("GUEST_TOOLS = {", "GUEST_TOOLS = {'play_music', 'stop_music', ", 1)
    open('owner.py', 'w', encoding='utf-8').write(o); print('owner ok')
