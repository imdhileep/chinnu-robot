import re
# ---------- dashboard: /api/blink (list) + /api/blink/{name}.jpg (snapshot) ----------
s = open('dashboard.py', encoding='utf-8').read()
if '/api/blink' not in s:
    s = s.replace("@app.post('/api/photo')", '''@app.get('/api/blink')
def api_blink_list():
    import blink_tool
    try: return {'ok': True, 'cameras': blink_tool.cameras()}
    except Exception as e: return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.get('/api/blink/{name}.jpg')
async def api_blink_snap(name: str):
    """Fresh snapshot from a Blink camera (takes ~10-20 s)."""
    import blink_tool, asyncio
    loop = asyncio.get_running_loop()
    try:
        cam, jpg = await loop.run_in_executor(None, blink_tool.snapshot, name)
        history.log('blink', cam)
        return Response(content=jpg, media_type='image/jpeg', headers={'X-Camera': cam, 'Cache-Control': 'no-store'})
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.post('/api/photo')''', 1)
    open('dashboard.py', 'w', encoding='utf-8').write(s); print('dashboard ok')

# ---------- brain: home_camera tool ----------
b = open('brain.py', encoding='utf-8').read()
if 'home_camera' not in b:
    tool = '''  {"type": "function", "function": {
    "name": "home_camera", "description": "Look through a HOME security camera (Blink): 'main door' (front door / outside) or 'patio' (back). Use when Chintu asks what is at the door, outside, patio, who came, is a package there, etc. Takes ~15 s. Optional question to focus on.",
    "parameters": {"type": "object", "properties": {"camera": {"type": "string", "enum": ["main door", "patio"]}, "question": {"type": "string"}}, "required": ["camera"]}}},
'''
    b = b.replace('  {"type": "function", "function": {\n    "name": "look",', tool + '  {"type": "function", "function": {\n    "name": "look",', 1)
    b = b.replace('        if name == "look":\n            return look(args.get("question", ""))\n',
                  '        if name == "look":\n            return look(args.get("question", ""))\n        if name == "home_camera":\n            return home_camera(args.get("camera", "main door"), args.get("question", ""))\n', 1)
    b = b.replace('def chat(user_text: str) -> str:', '''def _describe(jpg: bytes, question: str, where: str) -> dict:
    import base64
    b64 = base64.b64encode(jpg).decode()
    q = question or "Describe what you see in 1-3 short sentences."
    try:
        resp = client.chat.completions.create(model=CFG["model"], messages=[
            {"role": "system", "content": f"You are looking through a home security camera ({where}). Answer briefly and concretely in English (the caller will translate). Mention people, packages, vehicles, animals, anything unusual; describe people neutrally. Say if it is night/dark."},
            {"role": "user", "content": [{"type": "text", "text": q}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"}}]}],
            max_completion_tokens=200)
        return {"ok": True, "camera": where, "seen": resp.choices[0].message.content}
    except Exception as e:
        return {"ok": False, "error": f"vision error: {e}"}

def home_camera(camera: str = "main door", question: str = "") -> dict:
    """Fresh Blink snapshot via the dashboard, then describe it."""
    import requests
    try:
        r = requests.get(f"http://127.0.0.1:8080/api/blink/{camera}.jpg", timeout=60)
        if not r.ok or len(r.content) < 1000:
            return {"ok": False, "error": f"camera '{camera}' not available: {r.text[:120]}"}
    except Exception as e:
        return {"ok": False, "error": f"camera error: {e}"}
    return _describe(r.content, question, r.headers.get("X-Camera", camera))

def chat(user_text: str) -> str:''', 1)
    b = b.replace("EYES: you have a camera;", "HOME CAMERAS: home_camera('main door'|'patio') shows the front door / patio (Blink). EYES: you have a camera;", 1)
    open('brain.py', 'w', encoding='utf-8').write(b); print('brain ok', b.count('home_camera'))

# ---------- telegram: /blink [camera] ----------
t = open('telegram_bot.py', encoding='utf-8').read()
if '/blink' not in t:
    t = t.replace('/photo - camera snapshot', '/photo - camera snapshot\n/blink [main door|patio] - home camera snapshot (default both)', 1)
    t = t.replace("    if low.startswith('/look'):", '''    if low.startswith('/blink') or low.startswith('/door') or low.startswith('/patio'):
        arg = t.split(maxsplit=1)[1].strip().lower() if ' ' in t else ('patio' if low.startswith('/patio') else 'main door' if low.startswith('/door') else '')
        cams = [arg] if arg else ['main door', 'patio']
        send('Blink snapshot... (~15 s)')
        for c in cams:
            try:
                r = requests.get(f'{DASH}/api/blink/{c}.jpg', timeout=90)
                if r.ok and len(r.content) > 1000: send_photo(r.content, f"{r.headers.get('X-Camera', c)} {time.strftime('%H:%M:%S')}")
                else: send(f'{c}: not available ({r.text[:100]})')
            except Exception as e: send(f'{c}: error {e}')
        return
    if low.startswith('/look'):''', 1)
    open('telegram_bot.py', 'w', encoding='utf-8').write(t); print('telegram ok')

# ---------- mobile: Home cameras card on Home tab ----------
m = open('mobile.py', encoding='utf-8').read()
if 'blinkimg' not in m:
    m = m.replace(''' <div class="card"><h3>Chat</h3>''', ''' <div class="card"><h3>Home cameras</h3><div class="row"><button onclick="blink('main door')">&#128682; Main door</button><button onclick="blink('patio')">&#127795; Patio</button></div><div id="blinkbox" style="display:none;margin-top:8px"><img id="blinkimg" style="width:100%;border-radius:12px"><div id="blinkmsg" style="font-size:12px;color:var(--muted);margin-top:4px"></div></div></div>
 <div class="card"><h3>Chat</h3>''', 1)
    m = m.replace('<script>', '''<script>
async function blink(c){const b=document.getElementById('blinkbox');b.style.display='block';document.getElementById('blinkmsg').textContent=c+': loading (~15 s)...';
try{const r=await fetch('/api/blink/'+encodeURIComponent(c)+'.jpg?t='+Date.now());if(!r.ok)throw new Error(await r.text());const u=URL.createObjectURL(await r.blob());document.getElementById('blinkimg').src=u;document.getElementById('blinkmsg').textContent=(r.headers.get('X-Camera')||c)+' '+new Date().toLocaleTimeString()}catch(e){document.getElementById('blinkmsg').textContent='failed: '+e.message}}''', 1)
    open('mobile.py', 'w', encoding='utf-8').write(m); print('mobile ok')
