# ---------- dashboard ----------
s = open('dashboard.py', encoding='utf-8').read()
if '/api/faces' not in s:
    s = s.replace("@app.post('/api/photo')", '''@app.get('/api/faces')
def api_faces():
    import faces
    return {'ok': True, 'people': faces.people()}

@app.post('/api/faces/enroll')
async def api_faces_enroll(req: Request, name: str):
    """Body = raw JPEG/PNG bytes (phone upload). Enrols the largest face."""
    import faces
    data = await req.body()
    try:
        r = faces.enroll(name, data)
        if r.get('ok'): history.log('face', f'enrolled {name} ({r["count"]})')
        return r
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)

@app.post('/api/faces/enroll_cam')
def api_faces_enroll_cam(name: str):
    """Enrol from the robot camera right now."""
    import faces
    try:
        r = requests.get(f'{ROBOT}/snap.jpg', headers=HDR, timeout=8)
        res = faces.enroll(name, r.content)
        if res.get('ok'): history.log('face', f'enrolled {name} from camera ({res["count"]})')
        return res
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)

@app.get('/api/faces/identify')
def api_faces_identify():
    import faces
    try:
        r = requests.get(f'{ROBOT}/snap.jpg', headers=HDR, timeout=8)
        return faces.identify(r.content)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)

@app.post('/api/faces/forget')
def api_faces_forget(name: str):
    import faces
    history.log('face', f'forgot {name}')
    return faces.forget(name)

@app.post('/api/photo')''', 1)
    open('dashboard.py', 'w', encoding='utf-8').write(s); print('dashboard ok')

# ---------- brain ----------
b = open('brain.py', encoding='utf-8').read()
if 'enroll_face' not in b:
    tools = '''  {"type": "function", "function": {
    "name": "enroll_face", "description": "Learn/remember the face of the person in front of the camera under a name. Use when someone says 'nannu gurtu pettuko', 'remember my face', 'this is <name>, remember him'. Ask the name if not given. Default owner name is Chintu.",
    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
  {"type": "function", "function": {
    "name": "who_is_here", "description": "Check with face recognition who is in front of the camera right now (returns known names or 'unknown'). Use for 'evaru vunnaru?', 'nenu evarini?', 'do you know me?'.",
    "parameters": {"type": "object", "properties": {}}}},
'''
    b = b.replace('  {"type": "function", "function": {\n    "name": "look",', tools + '  {"type": "function", "function": {\n    "name": "look",', 1)
    b = b.replace('        if name == "look":\n            return look(args.get("question", ""))\n',
                  '''        if name == "look":
            return look(args.get("question", ""))
        if name == "enroll_face":
            import requests
            try:
                requests.post(robot.URL + "/head", headers=robot.HDR, params={"yaw": 0, "roll": 0, "pitch": 0}, timeout=5)
            except Exception: pass
            return requests.post("http://127.0.0.1:8080/api/faces/enroll_cam", params={"name": args.get("name", "Chintu")}, timeout=20).json()
        if name == "who_is_here":
            import requests
            try:
                requests.post(robot.URL + "/head", headers=robot.HDR, params={"yaw": 0, "roll": 0, "pitch": 0}, timeout=5)
            except Exception: pass
            r = requests.get("http://127.0.0.1:8080/api/faces/identify", timeout=20).json()
            if not r.get("faces"): r["note"] = "no face visible"
            return r
''', 1)
    # look(): add face-recognition hint to the vision prompt
    b = b.replace('''    b64 = base64.b64encode(r.content).decode()
    q = question or "Describe what you see in 1-3 short sentences."
    try:
        resp = client.chat.completions.create(model=CFG["model"], messages=[
            {"role": "system", "content": "You are the eyes of a small robot dog.''',
                  '''    b64 = base64.b64encode(r.content).decode()
    q = question or "Describe what you see in 1-3 short sentences."
    try:
        import faces
        hint = faces.describe(r.content)
    except Exception:
        hint = ""
    if hint:
        q = q + "\\n(" + hint + " Use these names for the people; Chintu is your owner/anna.)"
    try:
        resp = client.chat.completions.create(model=CFG["model"], messages=[
            {"role": "system", "content": "You are the eyes of a small robot dog.''', 1)
    b = b.replace("EYES: you have a camera;", "FACES: you recognise enrolled faces (who_is_here, enroll_face); greet Chintu by name when you see him. EYES: you have a camera;", 1)
    open('brain.py', 'w', encoding='utf-8').write(b); print('brain ok', b.count('faces'))

# ---------- settings page: Faces card ----------
st = open('settings.py', encoding='utf-8').read()
if 'facesCard' not in st:
    st = st.replace('<div class="card"><h3>Voice</h3>', '''<div class="card" id="facesCard"><h3>Faces (Chinnu evarini gurtu pattali)</h3><div id="faces"></div>
<div class="row"><input class="w" id="facename" placeholder="name (e.g. Chintu)" value="Chintu"><input type="file" id="facefiles" accept="image/*" multiple style="max-width:200px"><button onclick="faceUpload()">Upload photos</button><button onclick="faceCam()">From Chinnu camera</button></div>
<div id="facemsg" style="font-size:13px;color:var(--muted);margin-top:6px"></div></div>
<div class="card"><h3>Voice</h3>''', 1)
    st = st.replace('load();\n</script>', '''async function facesLoad(){const r=await (await fetch('/api/faces')).json();const p=r.people||{};$('faces').innerHTML=Object.keys(p).length?Object.entries(p).map(([n,c])=>'<div class="item"><span class="t">'+esc(n)+' <small>'+c+' photos</small></span><button class="x" onclick="faceDel(\\''+esc(n)+'\\')">forget</button></div>').join(''):'<div class="item"><small>nobody enrolled yet</small></div>'}
async function faceUpload(){const n=$('facename').value.trim();const fs=$('facefiles').files;if(!n||!fs.length){alert('name + photos kavali');return}let ok=0,bad=[];for(const f of fs){$('facemsg').textContent='uploading '+f.name+'...';const r=await (await fetch('/api/faces/enroll?name='+encodeURIComponent(n),{method:'POST',body:f})).json();if(r.ok)ok++;else bad.push(f.name+': '+r.error)}$('facemsg').textContent=ok+' enrolled'+(bad.length?' | failed: '+bad.join(', '):'');facesLoad()}
async function faceCam(){const n=$('facename').value.trim();if(!n)return;$('facemsg').textContent='Chinnu camera lo chustondi...';const r=await (await fetch('/api/faces/enroll_cam?name='+encodeURIComponent(n),{method:'POST'})).json();$('facemsg').textContent=r.ok?'enrolled from camera ('+r.count+')':'failed: '+r.error;facesLoad()}
async function faceDel(n){if(!confirm('forget '+n+'?'))return;await fetch('/api/faces/forget?name='+encodeURIComponent(n),{method:'POST'});facesLoad()}
load();facesLoad();
</script>''', 1)
    open('settings.py', 'w', encoding='utf-8').write(st); print('settings ok')

# ---------- telegram /who ----------
t = open('telegram_bot.py', encoding='utf-8').read()
if '/who' not in t:
    t = t.replace('/photo - camera snapshot', '/photo - camera snapshot\\n/who - who is in front of Chinnu (face recognition)', 1)
    t = t.replace("    if low.startswith('/look'):", '''    if low.startswith('/who'):
        r = api('GET', '/api/faces/identify')
        fs = r.get('faces') if isinstance(r, dict) else None
        send('Nobody visible.' if not fs else ', '.join(f"{f['name'] or 'unknown'} ({f['pos']}, {f['score']})" for f in fs)); return
    if low.startswith('/look'):''', 1)
    open('telegram_bot.py', 'w', encoding='utf-8').write(t); print('telegram ok')
