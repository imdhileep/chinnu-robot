m = open('mobile.py', encoding='utf-8').read()
if 'id="ptt"' in m: print('already'); raise SystemExit
R = []
def rep(a, b):
    assert a in m, a[:60]; R.append((a, b))

# 1) push-to-talk card on Home tab
rep(''' <div class="card"><div class="row"><button class="talk" onclick="post('/api/wake')">''',
''' <div class="card"><button id="ptt" class="talk" style="width:100%;padding:22px;font-size:18px">&#127897; Hold to talk (phone mic)</button><div id="pttmsg" style="font-size:13px;color:var(--muted);margin-top:6px;text-align:center">Hold, speak, release &mdash; Chinnu answers out loud</div></div>
 <div class="card"><div class="row"><button class="talk" onclick="post('/api/wake')">''')
# 2) devices cards at top of lights tab
rep('''<section class="tab" id="t-lights">\n''',
'''<section class="tab" id="t-lights">
 <div class="card"><h3>Govee plugs <button style="float:right;flex:none;padding:2px 10px;font-size:12px" onclick="devices(1)">&#8635;</button></h3><div id="govee" style="font-size:14px;color:var(--muted)">loading...</div></div>
 <div class="card"><h3>Power strip</h3><div id="strip" style="font-size:14px;color:var(--muted)">loading...</div></div>
''')
rep('''<span>&#128161;</span>Lights</button>''', '''<span>&#127968;</span>Devices</button>''')
rep("if(n==='server')srv()}", "if(n==='server')srv();if(n==='lights')devices()}")
# 3) links on server tab
rep(''' <div class="card"><h3>Server</h3><div class="kv" id="srv"></div></div>''',
''' <div class="card"><h3>Apps</h3><div class="row"><button onclick="location.href='https://chinnu-server.your-tailnet.ts.net'">&#9729; Nextcloud</button><button onclick="location.href='https://chinnu-server.your-tailnet.ts.net:8443'">&#127916; Jellyfin</button></div></div>
 <div class="card"><h3>Server</h3><div class="kv" id="srv"></div></div>''')
for a, b in R: m = m.replace(a, b, 1)

JS = r'''
let HOME={};const NICE={'chinnu server':'&#128421; Chinnu server','pidog charger':'&#128267; PiDog charger','modem':'&#127760; Modem','router':'&#128246; Router','google tv':'&#128250; Google TV','tv screen':'&#128250; TV','wireless charger':'&#9889; Wireless charger','empty':'(empty)'};
function sw(kind,t,label,on,locked){const btn=locked&&on?'<span style="font-size:12px;color:var(--muted)">&#128274; always on</span>':'<button style="flex:0 0 82px;padding:8px;font-size:14px;background:'+(on?'#1d5a3a':'#2a2f45')+'" onclick="plug(\''+kind+'\',\''+t+'\',\''+(on?'off':'on')+'\',this)">'+(on?'ON':'off')+'</button>';
 return '<div class="svc"><span class="dot'+(on?' ok':'')+'"></span><span class="n">'+label+'</span>'+btn+'</div>'}
async function devices(fresh){try{const s=await (await fetch('/api/home'+(fresh?'?fresh=1':''))).json();HOME=s;const L=new Set(s.locked||[]);let g='';
 if(s.govee){g+='<div class="row" style="margin-bottom:6px"><button onclick="plug(\'govee\',\'tv\',\'on\',this)">&#128250; TV on</button><button onclick="plug(\'govee\',\'tv\',\'off\',this)">TV off</button></div>';
  for(const[dev,st] of Object.entries(s.govee)){for(const[k,v] of Object.entries(st)){if(k==='online'||k==='empty')continue;g+=sw('govee',k,NICE[k]||k,!!v,L.has(k))}}}
 $('govee').innerHTML=g||('error: '+(s.govee_error||'?'));let t='';
 if(s.strip){for(const[k,v] of Object.entries(s.strip)){if(/empty/.test(v.name))continue;t+=sw('strip',k,v.name.replace(/ \(.*\)/,''),v.on,false)}}
 $('strip').innerHTML=t||('error: '+(s.strip_error||'?'))}catch(e){$('govee').textContent='offline'}}
async function plug(kind,t,a,b){if(kind==='strip'&&t==='3'&&a==='off'&&!confirm('Desktop PC power OFF?'))return;if(b)b.textContent='...';const r=await post('/api/plug/'+kind+'/'+encodeURIComponent(t)+'/'+a);if(r&&r.refused&&r.refused.length)alert('Protected: '+r.refused.join(', '));setTimeout(()=>devices(1),800)}
// phone push-to-talk (needs https -> tailscale link)
let rec=null,chunks=[];const P=$('ptt');
async function pttStart(e){e.preventDefault();if(rec)return;try{const st=await navigator.mediaDevices.getUserMedia({audio:true});const mt=MediaRecorder.isTypeSupported('audio/webm')?'audio/webm':'audio/mp4';
 rec=new MediaRecorder(st,{mimeType:mt});chunks=[];rec.ondataavailable=x=>chunks.push(x.data);rec.onstop=async()=>{st.getTracks().forEach(t=>t.stop());const blob=new Blob(chunks,{type:mt});rec=null;$('pttmsg').textContent='sending...';
 try{const r=await (await fetch('/api/voice',{method:'POST',headers:{'Content-Type':mt},body:blob})).json();$('pttmsg').textContent=r.text?'\u{1F5E3} '+r.text:'(nothing heard)'}catch(err){$('pttmsg').textContent='failed'}};
 rec.start();P.style.background='var(--bad)';$('pttmsg').textContent='listening... release to send'}catch(err){$('pttmsg').textContent='mic blocked: open the https tailscale link'}}
function pttStop(){if(rec&&rec.state==='recording')rec.stop();P.style.background=''}
P.addEventListener('pointerdown',pttStart);P.addEventListener('pointerup',pttStop);P.addEventListener('pointercancel',pttStop);P.addEventListener('pointerleave',pttStop);
'''
m = m.replace('setInterval(poll,2000);poll();', JS + 'setInterval(poll,2000);poll();', 1)
open('mobile.py', 'w', encoding='utf-8').write(m); print('frontend ok')
