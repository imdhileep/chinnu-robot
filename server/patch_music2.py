import shutil, time
ts = time.strftime('%H%M%S')
fn = 'music.py'; s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_pause' + ts)
rep = [
# remember source + offset, track real playback start
("_cur = {'title': None, 'source': None, 'stop': None, 'ffmpeg': None, 'started': None, 'queue': []}",
 "_cur = {'title': None, 'source': None, 'stop': None, 'ffmpeg': None, 'started': None, 'queue': [], 'src': None, 'offset': 0.0}\n_paused = {}"),
("def _player(src, title, stop_evt, delay):\n    if delay: time.sleep(delay)                 # let Chinnu finish saying \"playing ...\" first\n    if stop_evt.is_set(): return\n",
 "def _player(src, title, stop_evt, delay, offset=0.0):\n    if delay: time.sleep(delay)                 # let Chinnu finish saying \"playing ...\" first\n    if stop_evt.is_set(): return\n    seek = ['-ss', str(int(offset))] if offset > 1 else []\n    _cur['started'] = time.time(); _cur['offset'] = offset\n"),
("'-reconnect_streamed', '1', '-i', src,", "'-reconnect_streamed', '1', *seek, '-i', src,"),
("subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-i', src,", "subprocess.Popen(['ffmpeg', '-loglevel', 'error', *seek, '-i', src,"),
("def play(query, delay=4.0):\n    stop()\n",
 "def play(query, delay=4.0):\n    stop()\n    _paused.clear()\n"),
("        _cur.update(title=title, source=source, stop=ev, started=time.time())\n    threading.Thread(target=_player, args=(src, title, ev, delay), daemon=True).start()",
 "        _cur.update(title=title, source=source, stop=ev, started=time.time() + delay, src=src, offset=0.0)\n    threading.Thread(target=_player, args=(src, title, ev, delay), daemon=True).start()"),
("            'note': 'Say just one short line (e.g. \"playing <title>\") - the song starts in a few seconds. Saying \"Chinnu\" stops it.'}",
 "            'note': 'Say just one short line (e.g. \"playing <title>\") - the song starts in a few seconds. When Chintu says \"Chinnu\" the song pauses, you listen, then it continues.'}"),
]
for a, b in rep:
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)
s = s.replace("def stop():\n", "def stop():\n    _paused.clear()\n    return _halt()\n\ndef _halt():\n", 1)
s += '''

def pause():
    """Wake word heard: stop the audio but remember where we were, so the song can continue after the command."""
    if not _cur.get('title'): return {'ok': False}
    pos = _cur.get('offset', 0.0) + max(0.0, time.time() - (_cur.get('started') or time.time()))
    keep = {'src': _cur.get('src'), 'title': _cur.get('title'), 'source': _cur.get('source'), 'pos': pos}
    _halt()
    _paused.clear(); _paused.update(keep)
    print(f"[music] paused {keep['title']!r} at {int(pos)}s", flush=True)
    return {'ok': True, 'paused': keep['title']}

def resume_if_paused():
    """Called when the conversation is over: continue the paused song (unless it was stopped or replaced)."""
    if not _paused or _cur.get('title'): _paused.clear() if _cur.get('title') else None; return False
    p = dict(_paused); _paused.clear()
    ev = threading.Event()
    with _lock:
        _cur.update(title=p['title'], source=p['source'], stop=ev, started=time.time() + 0.5, src=p['src'], offset=p['pos'])
    threading.Thread(target=_player, args=(p['src'], p['title'], ev, 0.5, max(0.0, p['pos'] - 1.0)), daemon=True).start()
    print(f"[music] resumed {p['title']!r} at {int(p['pos'])}s", flush=True)
    return True
'''
open(fn, 'w', encoding='utf-8').write(s); print('music ok')

fn = 'voice_agent.py'; v = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_pause' + ts)
v = v.replace("            if music.is_playing(): music.stop()\n", "            if music.is_playing(): music.pause()\n", 1)
a = "    while True:\n        if not wait_wake():\n"
assert v.count(a) == 1, 'wait_wake anchor'
v = v.replace(a, "    while True:\n        try:\n            import music; music.resume_if_paused()   # conversation over -> continue the song\n        except Exception as e: print('[music]', e, flush=True)\n        if not wait_wake():\n", 1)
open(fn, 'w', encoding='utf-8').write(v); print('voice_agent ok')
