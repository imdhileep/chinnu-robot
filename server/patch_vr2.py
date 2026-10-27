import shutil, time
ts = time.strftime('%H%M%S')
# dashboard proxy for live gyro heading
fn = 'dashboard.py'
s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_vr2' + ts)
if "/api/move/last" not in s:
    a = "@app.post('/api/move/{direction}')"
    assert s.count(a) == 1
    s = s.replace(a, '''@app.get('/api/move/last')
def move_last():
    try: return requests.get(f'{ROBOT}/move/last', headers=HDR, timeout=3).json()
    except Exception as e: return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

''' + a)
    open(fn, 'w', encoding='utf-8').write(s); print('dashboard patched')

fn = 'vr.html'
s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak' + ts)
rep = [
("<li><b>Left stick</b> &mdash; walk: up forward, down back, left/right turn</li>",
 "<li><b>Left stick</b> &mdash; walk: up forward, down back, left/right turn</li>\n"
 "<li><b>Right stick up</b> &mdash; walk where you are looking (Chinnu turns its body to your look, then walks)</li>\n"
 "<li><b>Right stick down</b> &mdash; walk backward</li>"),
("// controllers\n",
 "// look-walk: turn body toward head direction using live gyro, shifting the head reference as the body turns\n"
 "let gyroPrev = null, gyroBusy = false;\n"
 "async function gyroDelta() {\n"
 "  if (gyroBusy) return 0; gyroBusy = true;\n"
 "  try { const r = await (await fetch('/api/move/last')).json(); const v = -(r.deg ? r.deg[0] : 0);\n"
 "    let d = gyroPrev === null || v < gyroPrev - 30 ? 0 : v - gyroPrev; gyroPrev = v; return d; }\n"
 "  catch (_) { return 0; } finally { gyroBusy = false; }\n"
 "}\n"
 "const ry = new THREE.Quaternion(), UP = new THREE.Vector3(0, 1, 0);\n"
 "function headYaw(xq) { if (!ref) return 0; q.copy(refInv).multiply(xq); e.setFromQuaternion(q, 'YXZ'); return YAW_SIGN * e.y * 180 / Math.PI; }\n"
 "// controllers\n"),
("    } else if (src.handedness === 'right') {\n",
 "    } else if (src.handedness === 'right') {\n"
 "      if (y < -0.5) { const hy = headYaw(xq); dir = Math.abs(hy) > 15 ? (hy > 0 ? 'turn_left' : 'turn_right') : 'forward'; lookWalk = true; }\n"
 "      else if (y > 0.5) dir = 'backward';\n"),
("  let dir = null;\n", "  let dir = null; lookWalk = false;\n"),
("let moving = null, moveT = 0, btnPrev = {};", "let moving = null, moveT = 0, btnPrev = {}, lookWalk = false;"),
("  if (dir) { if (dir !== moving || t - moveT > 300) { post('/api/move/' + dir + '?speed=100'); moveT = t;",
 "  if (dir && dir.startsWith('turn') && lookWalk) gyroDelta().then(d => { if (d) { ry.setFromAxisAngle(UP, -YAW_SIGN * d * Math.PI / 180); refInv.premultiply(ry); } });\n"
 "  if (!dir) gyroPrev = null;\n"
 "  if (dir) { if (dir !== moving || t - moveT > 300) { post('/api/move/' + dir + '?speed=100'); moveT = t;"),
]
for a, b in rep:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
open(fn, 'w', encoding='utf-8').write(s); print('vr patched')
