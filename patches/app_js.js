// ---------- Status / Alerts tabs (app v2) ----------
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function dur(sec){sec=Math.max(0,Math.round(sec));const d=Math.floor(sec/86400),h=Math.floor(sec%86400/3600),m=Math.floor(sec%3600/60);return d?d+'d '+h+'h':h?h+'h '+m+'m':m+'m'}
const GROUPS={core:'Chinnu core',ai:'AI models',home:'Home & network',media:'Media',auto:'Automations'};
let APP=null;
function strip(tl){if(!tl||!tl.length)return '';return '<div style="display:flex;gap:1px;height:10px;margin-top:6px">'+tl.map(v=>'<i style="flex:1;border-radius:1px;background:'+(v==null?'#1b2440':v>=.99?'var(--ok)':v>=.5?'var(--warn)':'var(--bad)')+'"></i>').join('')+'</div><div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted)"><span>24h ago</span><span>now</span></div>'}
function renderApp(r){APP=r;$('upbig').textContent=r.up+'/'+r.total;$('upbig').style.color=r.up===r.total?'var(--ok)':'var(--warn)';
 $('upsub').textContent='server '+(r.server_up||'').replace('up ','up ')+' · checked every minute';
 const m=r.modes||{};const tg=(name,on,label,extra)=>'<div class="svc"><span class="dot'+(on?' ok':'')+'"></span><span class="n">'+label+(extra?'<div style="font-size:12px;color:var(--muted)">'+esc(extra)+'</div>':'')+'</span><button style="flex:0 0 82px;padding:8px;font-size:14px;background:'+(on?'#1d5a3a':'#2a2f45')+'" onclick="modeSet(\''+name+'\',\''+(on?'off':'on')+'\')">'+(on?'ON':'off')+'</button></div>';
 const ro=(on,label,txt)=>'<div class="svc"><span class="dot'+(on?' ok':'')+'"></span><span class="n">'+label+'</span><span style="font-size:13px;color:var(--muted)">'+esc(txt)+'</span></div>';
 $('modes').innerHTML=tg('guard',m.guard,'&#128737; Guard mode',m.guard_note)+tg('follow',m.follow,'&#128062; Follow me')+tg('saver',m.saver,'&#128176; Saver mode','cheaper models, no realtime voice')+
  tg('owner',m.owner,'&#128275; Owner mode (its me)',m.owner?Math.ceil((m.owner_left||0)/60)+' min left':'guest rules now')+ro(m.presence==='home','&#127968; Presence',m.presence||'not set')+ro(m.quiet,'&#127769; Quiet hours',m.quiet?'on (11 PM-7 AM)':'off')+ro(m.charging,'&#128267; Charger',(m.charging?'charging':'not charging')+(m.battery!=null?' · '+m.battery+'%':''));
 let h='';for(const[g,gl] of Object.entries(GROUPS)){const fs=r.features.filter(f=>f.group===g);if(!fs.length)continue;const up=fs.filter(f=>f.ok).length;
  h+='<div class="card"><h3>'+gl+' <span style="float:right;color:'+(up===fs.length?'var(--ok)':'var(--warn)')+'">'+up+'/'+fs.length+'</span></h3>';
  for(const f of fs){const since=f.since?(f.ok?'up ':'down ')+dur(r.now-f.since):'';
   h+='<div style="padding:9px 0;border-bottom:1px solid #1b2440"><div style="display:flex;align-items:center;gap:8px"><span class="dot'+(f.ok?' ok':'')+'"></span><span style="flex:1;font-size:15px">'+esc(f.label)+'</span>'+
   (f.restart?'<button style="flex:0 0 auto;padding:6px 10px;font-size:12px" onclick="restartFeat(\''+f.key+'\',\''+esc(f.label)+'\',\''+f.restart+'\',this)">&#8635; restart</button>':'')+'</div>'+
   '<div style="font-size:12px;color:var(--muted);margin-left:18px">'+esc(f.note)+(since?' · '+since:'')+(f.d1!=null?' · 24h '+f.d1+'%':'')+(f.d7!=null?' · 7d '+f.d7+'%':'')+'</div>'+strip(f.tl)+'</div>'}
  h+='</div>'}
 $('feats').innerHTML=h;guardBox()}
async function appLoad(){try{renderApp(await (await fetch('/api/app/features')).json())}catch(e){$('upsub').textContent='could not load'}}
async function appCheck(){const b=$('chkb');b.textContent='checking…';try{renderApp(await (await fetch('/api/app/check',{method:'POST'})).json())}catch(e){}b.innerHTML='&#8635; Check now'}
async function restartFeat(k,label,rs,b){const warn=rs==='pidog'?'\n\nPiDog will be silent for about 1 minute.':rs==='dashboard'?'\n\nThe app reloads in ~15 seconds.':'';
 if(!confirm('Restart '+label+'?'+warn))return;b.textContent='…';const r=await post('/api/app/restart/'+k);b.innerHTML=r&&r.ok?'&#10003;':'&#10007;';
 if(rs==='dashboard')setTimeout(()=>location.reload(),15000);else setTimeout(appLoad,16000)}
async function modeSet(n,a){const u={guard:'/api/guard/'+a,follow:'/api/follow/'+a,saver:'/api/ops/saver/'+a,owner:'/api/owner/'+(a==='on'?'unlock':'lock')}[n];
 if(n==='follow'&&a==='on'&&!confirm('Chinnu will walk after you for up to 10 minutes. Start?'))return;await post(u);setTimeout(appLoad,600);if(n==='owner')ownGet()}
async function batChart(){try{const d=await (await fetch('/api/ops/battery')).json();if(!d.length){$('batchart').textContent='no data yet';return}
 const W=320,H=70,n=d.length,x=i=>n<2?W/2:i*(W-4)/(n-1)+2,y=p=>H-4-(p/100)*(H-8);let path=d.map((p,i)=>(i?'L':'M')+x(i).toFixed(1)+' '+y(p.pct).toFixed(1)).join(' ');
 const last=d[n-1];$('batnow').textContent=last.pct+'% · '+last.v+' V'+(last.charging?' · charging':'');
 $('batchart').innerHTML='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%;height:70px"><line x1="0" x2="'+W+'" y1="'+y(20)+'" y2="'+y(20)+'" stroke="#ff5a5f" stroke-dasharray="3 3" stroke-width="1"/><path d="'+path+'" fill="none" stroke="#4cc9f0" stroke-width="2"/></svg><div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted)"><span>'+d[0].t+'</span><span>'+last.t+'</span></div>'}catch(e){}}
async function spend(){try{const b=await (await fetch('/api/ops/budget')).json();$('spend').innerHTML='<span>today</span><span>$'+(b.today||0).toFixed(2)+' of $'+b.limits.daily_usd+'</span><span>this month</span><span>$'+(b.month||0).toFixed(2)+' of $'+b.limits.monthly_usd+'</span><span>saver</span><span>'+(b.saver?'ON':'off')+'</span>'}catch(e){}}
async function srv(){try{const s=await (await fetch('/api/server')).json();$('srv').innerHTML=['uptime','temp','load','mem','disk','tailscale','time'].map(k=>'<span>'+k+'</span><span>'+esc(s[k]||'-')+'</span>').join('')}catch(e){}}
function guardBox(){const m=(APP&&APP.modes)||{};$('guardbox').innerHTML=(m.guard?'<b style="color:var(--ok)">ON</b> · '+esc(m.guard_note||'watching'):'off')+(m.alerts?' · '+m.alerts+' alerts sent':'')+'<br>Turns on by itself when your iPhone leaves home Wi-Fi for 10 min, off when you come back.'}
async function blinkStatus(){try{const r=await (await fetch('/api/blink')).json();$('blinkst').innerHTML=(r.cameras||[]).map(c=>'<span class="dot'+(c.armed?' ok':'')+'"></span> '+esc(c.name)+': '+(c.armed?'armed':'not armed')+', battery '+esc(c.battery)+(c.battery==='low'?' &#9888;':'')).join('<br>')||'no cameras'}catch(e){$('blinkst').textContent='Blink not answering'}}
async function blink2(c){$('blinkbox2').style.display='block';$('blinkmsg2').textContent=c+': loading (~15 s)...';
 try{const r=await fetch('/api/blink/'+encodeURIComponent(c)+'.jpg?t='+Date.now());if(!r.ok)throw new Error(await r.text());$('blinkimg2').src=URL.createObjectURL(await r.blob());$('blinkmsg2').textContent=(r.headers.get('X-Camera')||c)+' '+new Date().toLocaleTimeString()}catch(e){$('blinkmsg2').textContent='failed: '+e.message}}
let REP=null;async function rep(w){REP=w;const t=$('reptxt');t.style.display='block';t.textContent='loading…';$('repsend').style.display='none';
 try{const u={brief:'/api/home_auto/briefing',night:'/api/ops/report',diary:'/api/summary'}[w];const r=await (await fetch(u)).json();t.textContent=r.text||r.summary||'(empty)';if(w!=='diary')$('repsend').style.display='flex'}catch(e){t.textContent='failed'}}
async function repSend(){const u={brief:'/api/home_auto/briefing?send=1',night:'/api/ops/report?send=1'}[REP];if(!u)return;await fetch(u);$('repsend').innerHTML='<button disabled>&#10003; Sent</button>';setTimeout(()=>$('repsend').innerHTML='<button onclick="repSend()">&#128228; Send to Telegram</button>',3000)}
const AICON={alert:'&#9888;',guard:'&#128737;',follow:'&#128062;',charge:'&#128267;',presence:'&#127968;',quiet:'&#127769;',routine:'&#9881;',blink:'&#128247;',face:'&#128100;',door:'&#128682;'};
async function alerts(){try{const r=await (await fetch('/api/app/alerts?days='+$('adays').value)).json();let last='';
 $('alist').innerHTML=r.items.map(a=>{let hd='';if(a.day!==last){last=a.day;hd='<div style="font-size:12px;color:var(--muted);margin:10px 0 4px;text-transform:uppercase;letter-spacing:.08em">'+a.day+'</div>'}
  const bad=/DOWN|OFFLINE|fail|seen at home|NOT MOUNTED|evaro/i.test(a.text);
  return hd+'<div style="display:flex;gap:8px;padding:6px 0;border-bottom:1px solid #1b2440"><span style="width:22px">'+(AICON[a.kind]||'&#8226;')+'</span><span style="flex:1;'+(bad?'color:#ff9a9e':'')+'">'+esc(a.text)+'</span><span style="font-size:12px;color:var(--muted)">'+esc(String(a.t).slice(0,5))+'</span></div>'}).join('')||'<span style="color:var(--muted)">No alerts &#127881;</span>'}catch(e){$('alist').textContent='could not load'}}
let wifiAll=false;
async function wifi(scan){try{if(scan)$('wifi').textContent='scanning (~20 s)…';const r=await (await fetch('/api/net/'+(scan?'scan':'devices'),{method:scan?'POST':'GET'})).json();
 $('wifin').textContent='· '+r.online+' online';$('wifimore').textContent=wifiAll?'Hide offline':'Show offline too ('+(r.total-r.online)+')';
 const ds=r.devices.filter(d=>wifiAll||d.online).sort((a,b)=>(b.online-a.online)||((b.label?1:0)-(a.label?1:0))||String(a.label||a.host||a.vendor).localeCompare(String(b.label||b.host||b.vendor)));
 $('wifi').innerHTML=ds.map(d=>'<div class="svc" onclick="labelDev(\''+d.mac+'\',\''+esc(d.label||'').replace(/'/g,'')+'\')"><span class="dot'+(d.online?' ok':'')+'"></span><span class="n">'+esc(d.label||d.host||d.vendor||d.mac)+'<div style="font-size:11px;color:var(--muted)">'+esc(d.ip||'offline')+(d.vendor?' · '+esc(d.vendor):'')+'</div></span><span style="font-size:12px;color:var(--muted)">'+(d.today_min!=null?dur(d.today_min*60)+' today':'')+'</span></div>').join('')}catch(e){$('wifi').textContent='could not load'}}
async function labelDev(mac,cur){const n=prompt('Name for this device ('+mac+'):',cur);if(n===null)return;await fetch('/api/net/label',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mac,label:n.trim()})});wifi()}
function tab(n,b){document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));$('t-'+n).classList.add('on');document.querySelectorAll('nav button').forEach(x=>x.classList.remove('on'));b.classList.add('on');
 if(n==='server'){appLoad();srv();batChart();spend()}if(n==='lights'){devices();wifi()}if(n==='alerts'){appLoad();alerts();blinkStatus()}}
setInterval(()=>{const t=document.querySelector('.tab.on');if(!t||document.hidden)return;if(t.id==='t-server')appLoad();if(t.id==='t-alerts')alerts()},30000);
