p = 'mobile.py'; s = open(p, encoding='utf-8').read()
card = r''' <div class="card" id="speedcard"><h3>&#128246; Speed regulator <span id="spdsum" style="float:right;text-transform:none;letter-spacing:0"></span></h3>
  <div style="font-size:13px;color:var(--muted);margin-bottom:8px">Works for devices on <b style="color:var(--fg)">Chinnu-WiFi</b>. Join it with the QR, then pick a speed for each device.</div>
  <div class="row"><button onclick="wpass()" id="wpb">&#128273; Show password</button><button onclick="wqr()">&#128247; Join QR</button></div>
  <div id="wqr" style="display:none;text-align:center;margin:6px 0 10px"><img id="wqrimg" style="width:220px;max-width:80%;border-radius:12px;background:#fff;padding:6px"><div style="font-size:12px;color:var(--muted)">Scan with the other phone's camera &rarr; Join "Chinnu-WiFi"</div></div>
  <div id="spd" style="font-size:14px"></div></div>
'''
anchor = ' <div class="card"><h3>Wi-Fi devices'
assert s.count(anchor) == 1; s = s.replace(anchor, card + anchor)

js = r'''
// ---------- Speed regulator ----------
const SPEEDS=[[0,'No limit'],[25,'25'],[10,'10'],[5,'5'],[3,'3'],[1,'1'],[0.064,'&#9208; Pause']];
let WPW='';
async function wpass(){if(!WPW){try{WPW=(await (await fetch('/api/wifi/clients')).json()).password||''}catch(e){}}
 const b=$('wpb');if(b.dataset.on){b.innerHTML='&#128273; Show password';delete b.dataset.on}else{b.innerHTML=esc(WPW)+' &nbsp;&#128203;';b.dataset.on=1;try{navigator.clipboard.writeText(WPW)}catch(e){}}}
function wqr(){const q=$('wqr');if(q.style.display==='block'){q.style.display='none';return}$('wqrimg').src='/api/wifi/qr.svg?t='+Date.now();q.style.display='block'}
function mb(x){return x==null?'–':x>=10?x.toFixed(0):x.toFixed(1)}
async function speedLoad(){try{const r=await (await fetch('/api/wifi/clients')).json();const ds=r.devices||[];const on=ds.filter(d=>d.online);
 const tot=on.reduce((a,d)=>a+(d.now_down||0),0);$('spdsum').textContent=on.length+' connected · '+mb(tot)+' Mbps now';
 if(!ds.length){$('spd').innerHTML='<div style="color:var(--muted);padding:6px 0">Inka evaru Chinnu-WiFi lo levu. Join QR chupinchi connect cheyinchu.</div>';return}
 $('spd').innerHTML=ds.map(d=>{const lim=d.down||0;const nm=esc(d.label||d.mac);
  const chips=SPEEDS.map(([v,l])=>{const sel=(v===0&&!lim)||(v&&Math.abs(lim-v)<0.001);return '<button style="flex:1;padding:8px 0;font-size:13px;'+(sel?'background:var(--accent);color:#000':'')+'" onclick="setSpeed(\''+d.mac+'\','+v+',\''+nm.replace(/'/g,'')+'\')">'+l+'</button>'}).join('');
  return '<div style="padding:10px 0;border-bottom:1px solid #1b2440'+(d.online?'':';opacity:.5')+'"><div style="display:flex;align-items:center;gap:8px"><span class="dot'+(d.online?' ok':'')+'"></span><span style="flex:1" onclick="renameSpd(\''+d.mac+'\',\''+nm.replace(/'/g,'')+'\')">'+nm+' <span style="font-size:11px;color:var(--muted)">&#9998;</span><div style="font-size:11px;color:var(--muted)">'+esc(d.ip||'offline')+(d.mb?' · '+mb(d.mb)+' MB used':'')+'</div></span>'+
   '<span style="text-align:right;font-size:13px">&#8595; '+mb(d.now_down)+' <span style="color:var(--muted)">Mbps</span><br>&#8593; '+mb(d.now_up)+'</span></div>'+
   '<div style="font-size:11px;color:var(--muted);margin:6px 0 4px">Limit: <b style="color:var(--fg)">'+(lim? (lim<0.1?'paused':lim+' Mbps'):'none')+'</b></div><div class="row" style="gap:4px">'+chips+'</div></div>'}).join('')}catch(e){$('spd').textContent='could not load'}}
async function setSpeed(mac,v,nm){if(v&&v<0.1&&!confirm('Pause internet for '+nm+'?'))return;
 await fetch('/api/wifi/limit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mac,down:v,up:v})});speedLoad()}
async function renameSpd(mac,cur){const n=prompt('Name for this device:',cur);if(n===null)return;
 await fetch('/api/wifi/limit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mac,label:n.trim()})});speedLoad()}
setInterval(()=>{const t=document.querySelector('.tab.on');if(t&&t.id==='t-lights'&&!document.hidden)speedLoad()},3000);
'''
k = 'setInterval(poll,2000);poll();'
assert s.count(k) == 1; s = s.replace(k, js + k)
old = "if(n==='lights'){devices();wifi()}"
assert s.count(old) == 1; s = s.replace(old, "if(n==='lights'){devices();wifi();speedLoad()}")
open(p, 'w', encoding='utf-8').write(s); print('ok')
