import shutil, time
fn = 'vr.html'
s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak3' + time.strftime('%H%M%S'))
rep = [
('<button id="go" disabled>Loading...</button>',
 '<button id="goar" disabled>Loading...</button>\n<button id="go" disabled style="background:#333;color:#e8ecf4">Enter VR (full)</button>'),
('#go:disabled{background:#333;color:#888}',
 '#go:disabled,#goar:disabled{background:#333;color:#888}\n#goar{display:block;width:100%;padding:18px;margin:14px 0 0;font-size:20px;border:0;border-radius:12px;background:var(--accent);color:#000;font-weight:700}'),
("<li><b>Right trigger</b> &mdash; Chinnu wags tail</li>",
 "<li><b>Right trigger</b> &mdash; Chinnu wags tail</li>\n<li><b>X</b> (left) &mdash; Chinnu screen size: small / big / hidden</li>"),
("const renderer = new THREE.WebGLRenderer({antialias: true});",
 "const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true});"),
("const scene = new THREE.Scene(); scene.background = new THREE.Color(0x05070d);",
 "const scene = new THREE.Scene(); const BG = new THREE.Color(0x05070d); scene.background = BG;"),
("    if (src.handedness === 'left') {\n",
 "    if (src.handedness === 'left') {\n      if (edge('X', pressed(src, 4))) cycleSize();\n"),
("// head tracking\n",
 "// screen sizes (reality mode starts small so you can see the room)\n"
 "const SIZES = [[0.55, -0.35, 'small'], [1, 0, 'big'], [0, 0, 'hidden']]; let sizeI = 1;\n"
 "function setSize(i) { sizeI = i; const [k, dy, n] = SIZES[i]; screen.visible = k > 0; if (k) { screen.scale.set(k, k, 1); screen.position.set(0, dy, -2.2); } hud.position.set(0, k ? dy - 0.9 * k - 0.25 : -0.6, -2.2); st('Screen ' + n); }\n"
 "function cycleSize() { setSize((sizeI + 1) % SIZES.length); }\n"
 "// head tracking\n"),
("const go = $('go');\nif (!navigator.xr) { go.textContent = 'Open this page in the Quest browser'; }\nelse navigator.xr.isSessionSupported('immersive-vr').then(ok => {\n  if (!ok) { go.textContent = 'VR not supported here'; return; }\n  go.disabled = false; go.textContent = 'Enter VR';\n  go.onclick = async () => {\n    const s = await navigator.xr.requestSession('immersive-vr', {optionalFeatures: ['local-floor']});\n",
 "const go = $('go'), goar = $('goar');\n"
 "async function start(mode) {\n"
 "    const ar = mode === 'immersive-ar';\n"
 "    scene.background = ar ? null : BG; setSize(ar ? 0 : 1);\n"
 "    const s = await navigator.xr.requestSession(mode, {optionalFeatures: ['local-floor']});\n"),
("    s.addEventListener('end', () => { post('/api/move/stop'); post('/api/head?yaw=0&pitch=0&roll=0'); st('Exited VR'); });\n  };\n});",
 "    s.addEventListener('end', () => { post('/api/move/stop'); post('/api/head?yaw=0&pitch=0&roll=0'); scene.background = BG; st('Exited'); });\n}\n"
 "if (!navigator.xr) { goar.textContent = go.textContent = 'Open this page in the Quest browser'; }\n"
 "else {\n"
 "  navigator.xr.isSessionSupported('immersive-ar').then(ok => { goar.disabled = !ok; goar.textContent = ok ? 'Enter Reality mode' : 'Reality mode not supported'; goar.onclick = () => start('immersive-ar'); });\n"
 "  navigator.xr.isSessionSupported('immersive-vr').then(ok => { go.disabled = !ok; go.onclick = () => start('immersive-vr'); });\n"
 "}"),
]
for a, b in rep:
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)
open(fn, 'w', encoding='utf-8').write(s); print('ok')
