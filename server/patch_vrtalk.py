import shutil, time
fn = 'vr.html'
s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_talk' + time.strftime('%H%M%S'))
rep = [
("<li><b>X</b> (left) &mdash; Chinnu screen size: small / big / hidden</li>",
 "<li><b>X</b> (left) &mdash; Chinnu screen size: small / big / hidden</li>\n<li><b>Left trigger (hold)</b> &mdash; talk to Chinnu; the answer plays in your headset</li>"),
("// controllers\n",
 "// talk: hold left trigger -> record Quest mic -> /api/glasses/talk -> play reply in headset\n"
 "let micStream = null, rec = null, chunks = [], talkHeld = false, talking = false;\n"
 "async function initMic() { try { micStream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}}); } catch (e) { st('Mic blocked - talk disabled'); } }\n"
 "function talkStart() {\n"
 "  if (!micStream || talking) return; chunks = [];\n"
 "  const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';\n"
 "  rec = new MediaRecorder(micStream, mime ? {mimeType: mime} : undefined);\n"
 "  rec.ondataavailable = ev => { if (ev.data.size) chunks.push(ev.data); };\n"
 "  rec.onstop = sendTalk; rec.start(); st('🎤 Listening... release to send');\n"
 "}\n"
 "function talkStop() { if (rec && rec.state === 'recording') rec.stop(); }\n"
 "async function sendTalk() {\n"
 "  const blob = new Blob(chunks, {type: chunks[0] ? chunks[0].type : 'audio/webm'});\n"
 "  if (blob.size < 2000) { st('Too short - hold the trigger while you speak'); return; }\n"
 "  talking = true; st('Chinnu thinking...');\n"
 "  const fd = new FormData(); fd.append('audio', blob, 'q.webm'); fd.append('wake', '0');\n"
 "  try {\n"
 "    const r = await fetch('/api/glasses/talk', {method: 'POST', body: fd});\n"
 "    const dec = h => { try { return decodeURIComponent(r.headers.get(h) || ''); } catch (_) { return ''; } };\n"
 "    if (r.status === 200) { const reply = dec('X-Reply'); st(reply ? ('Chinnu: ' + reply).slice(0, 70) : 'Chinnu speaking...');\n"
 "      const a = new Audio(URL.createObjectURL(await r.blob())); a.onended = () => { talking = false; }; await a.play(); }\n"
 "    else { talking = false; st(r.status === 204 ? 'Did not catch that - try again' : 'Server error ' + r.status); }\n"
 "  } catch (e) { talking = false; st('Network error'); }\n"
 "}\n"
 "// controllers\n"),
("      if (edge('X', pressed(src, 4))) cycleSize();\n",
 "      if (edge('X', pressed(src, 4))) cycleSize();\n"
 "      const lt = pressed(src, 0);\n"
 "      if (lt && !talkHeld) talkStart(); else if (!lt && talkHeld) talkStop();\n"
 "      talkHeld = lt;\n"),
("st('Ready');\n", "st('Ready');\ninitMic();\n"),
]
for a, b in rep:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
open(fn, 'w', encoding='utf-8').write(s); print('ok')
