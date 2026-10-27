"""Chinnu settings page (/settings): edit commands.yaml, view/delete memory, reminders, schedules, voice config.
Included by dashboard.py via app.include_router(settings.router)."""
import os, yaml, json, time, subprocess
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
BASE = os.path.dirname(os.path.abspath(__file__))
CMD_FILE = os.path.join(BASE, 'commands.yaml')
CFG_FILE = os.path.join(BASE, 'config.yaml')

@router.get('/api/settings')
def get_settings():
    import extras, commands
    cfg = yaml.safe_load(open(CFG_FILE, encoding='utf-8')) or {}
    return {'commands_yaml': open(CMD_FILE, encoding='utf-8').read(), 'commands': commands.names(), 'scheduled': commands.scheduled(),
            'idle': cfg.get('idle', {}), 'memory': extras.facts(), 'reminders': extras.list_reminders()['reminders'], 'voice': cfg.get('voice', {}), 'brain': cfg.get('brain', {})}

@router.post('/api/settings/commands')
async def save_commands(req: Request):
    text = (await req.json()).get('text', '')
    try:
        data = yaml.safe_load(text) or {}
        assert isinstance(data, dict), 'top level must be a mapping of command names'
    except Exception as e:
        return JSONResponse({'ok': False, 'error': f'YAML error: {e}'}, status_code=400)
    bak = CMD_FILE + '.' + time.strftime('%Y%m%d%H%M%S') + '.bak'
    os.replace(CMD_FILE, bak) if os.path.exists(CMD_FILE) else None
    open(CMD_FILE, 'w', encoding='utf-8').write(text)
    return {'ok': True, 'commands': list(k for k in data if not str(k).startswith('_')), 'backup': os.path.basename(bak)}

@router.post('/api/settings/memory/delete')
async def mem_delete(req: Request):
    import extras
    return extras.forget((await req.json()).get('text', ''))

@router.post('/api/settings/memory/add')
async def mem_add(req: Request):
    import extras
    return extras.remember((await req.json()).get('text', ''))

@router.post('/api/settings/reminder/cancel')
async def rem_cancel(req: Request):
    import extras
    d = await req.json(); return extras.cancel_reminder(d.get('id'), d.get('text'))

@router.post('/api/settings/reminder/add')
async def rem_add(req: Request):
    import extras
    d = await req.json(); return extras.set_reminder(d.get('text', ''), d.get('minutes'), d.get('at'))

@router.post('/api/settings/idle')
async def save_idle(req: Request):
    d = await req.json()
    cfg = yaml.safe_load(open(CFG_FILE, encoding='utf-8-sig')) or {}
    i = cfg.setdefault('idle', {})
    for k in ('enabled', 'greet', 'greet_unknown', 'track'):
        if k in d: i[k] = bool(d[k])
    for k in ('min_gap', 'max_gap', 'greet_cooldown', 'face_interval'):
        if d.get(k) not in (None, ''): i[k] = float(d[k])
    if d.get('quiet') is not None: i['quiet'] = str(d['quiet'])
    open(CFG_FILE, 'w', encoding='utf-8').write(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))
    subprocess.Popen(['sudo', 'systemctl', 'restart', 'chinnu-voice'])
    return {'ok': True, 'idle': i, 'note': 'voice service restarting'}

@router.post('/api/settings/voice')
async def save_voice(req: Request):
    d = await req.json()
    cfg = yaml.safe_load(open(CFG_FILE, encoding='utf-8')) or {}
    v = cfg.setdefault('voice', {})
    for k in ('listen_seconds', 'followup_seconds', 'silence_rms', 'child_pitch', 'voice'):
        if k in d and d[k] not in (None, ''):
            v[k] = float(d[k]) if k != 'voice' else str(d[k])
    if 'child_voice' in d: v['child_voice'] = bool(d['child_voice'])
    open(CFG_FILE, 'w', encoding='utf-8').write(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))
    subprocess.Popen(['sudo', 'systemctl', 'restart', 'chinnu-voice'])
    return {'ok': True, 'voice': v, 'note': 'voice service restarting'}

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Chinnu settings</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>
:root{--bg:#0b0f1a;--card:#10162a;--fg:#e8ecf4;--muted:#8a93a8;--accent:#4cc9f0;--ok:#3ddc84;--bad:#ff5a5f}
*{box-sizing:border-box;margin:0;padding:0}body{background:var(--bg);color:var(--fg);font-family:-apple-system,system-ui,Roboto,sans-serif;padding:12px;padding-top:calc(12px + env(safe-area-inset-top))}
a{color:var(--accent);text-decoration:none}#top{display:flex;gap:14px;align-items:center;margin-bottom:12px}h1{font-size:18px;flex:1}
.card{background:var(--card);border-radius:16px;padding:12px;margin-bottom:12px}h3{font-size:12px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase;margin-bottom:8px}
textarea{width:100%;min-height:320px;background:#0e1424;color:#d7e0ff;border:1px solid #1b2440;border-radius:10px;padding:10px;font:13px/1.4 ui-monospace,Menlo,monospace;white-space:pre;overflow:auto}
button{font-size:14px;padding:10px 14px;border:0;border-radius:10px;background:#1f2a48;color:var(--fg);font-weight:600}button.ok{background:#1d3a2a}button.x{background:#5a2030;padding:6px 10px;font-size:12px}
.row{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}.item{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #1b2440;font-size:14px}.item:last-child{border:0}.item .t{flex:1}.item small{color:var(--muted)}
input{font-size:14px;padding:10px;border-radius:10px;border:1px solid #1b2440;background:#0e1424;color:var(--fg)}input.w{flex:1;min-width:120px}
#msg{font-size:13px;color:var(--muted);margin-top:6px}.kv{display:grid;grid-template-columns:auto 1fr;gap:6px 12px;font-size:14px;align-items:center}.kv span{color:var(--muted)}.kv input{width:100%}
</style></head><body>
<div id="top"><a href="/m">&larr; Chinnu</a><h1>Settings</h1></div>
<div class="card"><h3>Commands &amp; schedules (commands.yaml)</h3><textarea id="yaml" spellcheck="false"></textarea>
<div class="row"><button class="ok" onclick="saveYaml()">Save</button><button onclick="load()">Reload</button><span id="msg"></span></div>
<div id="sched" style="margin-top:8px;font-size:13px;color:var(--muted)"></div></div>
<div class="card"><h3>Memory (Chinnu gurtu pettukunnavi)</h3><div id="mem"></div>
<div class="row"><input class="w" id="memtxt" placeholder="new fact..."><button onclick="memAdd()">Add</button></div></div>
<div class="card"><h3>Reminders</h3><div id="rem"></div>
<div class="row"><input class="w" id="remtxt" placeholder="reminder text"><input id="remat" placeholder="HH:MM or minutes" style="width:140px"><button onclick="remAdd()">Add</button></div></div>
<div class="card" id="facesCard"><h3>Faces (Chinnu evarini gurtu pattali)</h3><div id="faces"></div>
<div class="row"><input class="w" id="facename" placeholder="name (e.g. Chintu)" value="Chintu"><input type="file" id="facefiles" accept="image/*" multiple style="max-width:200px"><button onclick="faceUpload()">Upload photos</button><button onclick="faceCam()">From Chinnu camera</button></div>
<div id="facemsg" style="font-size:13px;color:var(--muted);margin-top:6px"></div></div>
<div class="card"><h3>Idle behaviours &amp; greeting</h3><div class="kv" id="idle"></div><div class="row"><button class="ok" onclick="saveIdle()">Save &amp; restart voice</button></div></div>
<div class="card"><h3>Voice</h3><div class="kv" id="voice"></div><div class="row"><button class="ok" onclick="saveVoice()">Save &amp; restart voice</button></div></div>
<script>
const $=id=>document.getElementById(id);
async function post(u,b){return await (await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})})).json()}
let S=null;
async function load(){S=await (await fetch('/api/settings')).json();$('yaml').value=S.commands_yaml;
$('sched').textContent='Scheduled: '+(Object.keys(S.scheduled).length?Object.entries(S.scheduled).map(([k,v])=>k+' @ '+v.at+(v.days.length?' ('+v.days.join(',')+')':'')).join(' · '):'none');
$('mem').innerHTML=S.memory.length?S.memory.map(f=>'<div class="item"><span class="t">'+esc(f.text)+' <small>'+f.at+'</small></span><button class="x" onclick="memDel(\''+esc(f.text).replace(/'/g,"\\'")+'\')">delete</button></div>').join(''):'<div class="item"><small>empty</small></div>';
$('rem').innerHTML=S.reminders.length?S.reminders.map(r=>'<div class="item"><span class="t">'+esc(r.text)+' <small>'+r.when+'</small></span><button class="x" onclick="remDel('+r.id+')">cancel</button></div>').join(''):'<div class="item"><small>none</small></div>';
const I=S.idle||{};$('idle').innerHTML=[['enabled','idle actions (head look / tilt / stretch)','chk'],['greet','greet known faces','chk'],['greet_unknown','ask unknown faces','chk'],['track','head follows faces','chk'],['min_gap','min gap (s)'],['max_gap','max gap (s)'],['quiet','quiet hours (HH:MM-HH:MM)'],['greet_cooldown','greet cooldown (s)'],['face_interval','face check every (s)']].map(([k,l,t])=>'<span>'+l+'</span>'+(t==='chk'?'<input type="checkbox" id="i_'+k+'" '+(I[k]?'checked':'')+' style="width:22px;height:22px">':'<input id="i_'+k+'" value="'+(I[k]??'')+'">')).join('');
const v=S.voice;$('voice').innerHTML=[['listen_seconds','max listen (s)'],['followup_seconds','follow-up listen (s)'],['silence_rms','silence RMS'],['child_pitch','pitch (cents)'],['voice','TTS voice']].map(([k,l])=>'<span>'+l+'</span><input id="v_'+k+'" value="'+(v[k]??'')+'">').join('')}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')}
async function saveYaml(){const r=await post('/api/settings/commands',{text:$('yaml').value});$('msg').textContent=r.ok?'saved ('+r.commands.length+' commands)':r.error;if(r.ok)load()}
async function memDel(t){await post('/api/settings/memory/delete',{text:t});load()}
async function memAdd(){const t=$('memtxt').value.trim();if(!t)return;await post('/api/settings/memory/add',{text:t});$('memtxt').value='';load()}
async function remDel(id){await post('/api/settings/reminder/cancel',{id});load()}
async function remAdd(){const t=$('remtxt').value.trim(),a=$('remat').value.trim();if(!t||!a)return;const b={text:t};if(/^\d+$/.test(a))b.minutes=+a;else b.at=a;const r=await post('/api/settings/reminder/add',b);$('remat').value='';$('remtxt').value='';if(!r.ok)alert(r.error);load()}
async function saveIdle(){const b={};['enabled','greet','greet_unknown','track'].forEach(k=>b[k]=$('i_'+k).checked);['min_gap','max_gap','quiet','greet_cooldown','face_interval'].forEach(k=>b[k]=$('i_'+k).value);const r=await post('/api/settings/idle',b);alert(r.ok?'saved, voice restarting':JSON.stringify(r))}
async function saveVoice(){const b={};['listen_seconds','followup_seconds','silence_rms','child_pitch','voice'].forEach(k=>b[k]=$('v_'+k).value);const r=await post('/api/settings/voice',b);alert(r.ok?'saved, voice restarting':JSON.stringify(r))}
async function facesLoad(){const r=await (await fetch('/api/faces')).json();const p=r.people||{};$('faces').innerHTML=Object.keys(p).length?Object.entries(p).map(([n,c])=>'<div class="item"><span class="t">'+esc(n)+' <small>'+c+' photos</small></span><button class="x" onclick="faceDel(\''+esc(n)+'\')">forget</button></div>').join(''):'<div class="item"><small>nobody enrolled yet</small></div>'}
async function faceUpload(){const n=$('facename').value.trim();const fs=$('facefiles').files;if(!n||!fs.length){alert('name + photos kavali');return}let ok=0,bad=[];for(const f of fs){$('facemsg').textContent='uploading '+f.name+'...';const r=await (await fetch('/api/faces/enroll?name='+encodeURIComponent(n),{method:'POST',body:f})).json();if(r.ok)ok++;else bad.push(f.name+': '+r.error)}$('facemsg').textContent=ok+' enrolled'+(bad.length?' | failed: '+bad.join(', '):'');facesLoad()}
async function faceCam(){const n=$('facename').value.trim();if(!n)return;$('facemsg').textContent='Chinnu camera lo chustondi...';const r=await (await fetch('/api/faces/enroll_cam?name='+encodeURIComponent(n),{method:'POST'})).json();$('facemsg').textContent=r.ok?'enrolled from camera ('+r.count+')':'failed: '+r.error;facesLoad()}
async function faceDel(n){if(!confirm('forget '+n+'?'))return;await fetch('/api/faces/forget?name='+encodeURIComponent(n),{method:'POST'});facesLoad()}
load();facesLoad();
</script></body></html>"""

@router.get('/settings', response_class=HTMLResponse)
def settings_page():
    return PAGE
