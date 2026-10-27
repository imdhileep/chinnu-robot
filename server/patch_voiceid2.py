import shutil, time
ts = time.strftime('%H%M%S')
def patch(fn, pairs):
    s = open(fn, encoding='utf-8').read(); shutil.copy(fn, f'{fn}.bak_vid2{ts}')
    for a, b in pairs:
        assert s.count(a) == 1, (fn, a[:50]); s = s.replace(a, b)
    open(fn, 'w', encoding='utf-8').write(s); print('patched', fn)

patch('speaker.py', [
("THRESH = 0.55\nLOW = 0.35\n", "THRESH = 0.48\nLOW = 0.30\nADAPT = 0.56          # confident live matches are learned (room/mic conditions)\nMAX_LIVE = 40\nlast_secs = 0.0\n"),
("def embed(wav_bytes):\n    x = _pcm16k(wav_bytes)\n",
 "def embed(wav_bytes):\n    global last_secs\n    x = _pcm16k(wav_bytes)\n    last_secs = len(x) / 16000.0\n"),
("def forget(name):",
 "def adapt(name, wav_bytes, base=8):\n    \"\"\"Add a confidently-matched live clip; keep the first `base` enrolment clips + newest MAX_LIVE.\"\"\"\n"
 "    v = embed(wav_bytes)\n    if v is None: return\n    db = _load(); e = db.setdefault(name, [])\n"
 "    e.append(v.round(5).tolist())\n    if len(e) > base + MAX_LIVE: del e[base:len(e) - MAX_LIVE]\n"
 "    DB.write_text(json.dumps(db))\n\ndef forget(name):"),
])
patch('voice_agent.py', [
("        if vname == 'Chintu':\n            is_owner = True\n",
 "        if vname == 'Chintu':\n            is_owner = True\n"
 "            if vscore >= speaker.ADAPT: threading.Thread(target=speaker.adapt, args=('Chintu', wav), daemon=True).start()\n"),
("        elif 0 < vscore < speaker.LOW:\n",
 "        elif 0 < vscore < speaker.LOW and speaker.last_secs >= 1.5:\n"),
])
