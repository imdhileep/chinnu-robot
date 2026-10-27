import shutil
P = '/home/dk/chinnu-agent/mobile.py'
shutil.copy(P, P + '.bak_glasses')
m = open(P, encoding='utf-8').read()

# ---------- backend: transcribe -> chat (no PiDog speech) -> TTS audio back to the phone ----------
anchor = "@router.get('/m', response_class=HTMLResponse)"
assert anchor in m
m = m.replace(anchor, '''@router.post('/api/voice_reply')
async def phone_voice_reply(request: Request):
    """Glasses / phone mode: audio blob -> transcript -> Chinnu's reply as text + audio, played on the phone
    (so it comes out of Bluetooth glasses/earbuds) instead of the PiDog speaker."""
    import io, base64, asyncio, requests as _rq, voice
    body = await request.body()
    ct = request.headers.get('content-type', 'audio/webm')
    ext = 'mp4' if 'mp4' in ct or 'm4a' in ct or 'aac' in ct else ('ogg' if 'ogg' in ct else 'webm')
    if len(body) < 2000: return {'ok': False, 'error': 'too short', 'text': ''}
    def work():
        f = io.BytesIO(body); f.name = f'phone.{ext}'
        text = voice.client.audio.transcriptions.create(model='gpt-4o-transcribe', file=f, language='te').text.strip()
        if not text: return {'ok': True, 'text': ''}
        try: reply = _rq.post('http://127.0.0.1:8081/chat', json={'text': text, 'speak': False}, timeout=120).json().get('reply') or 'Ok anna'
        except Exception: reply = 'Chinnu busy ga vundi anna, malli try cheyi'
        out = {'ok': True, 'text': text, 'reply': reply}
        try:
            p = voice.tts(reply, '/tmp/chinnu_glasses_tts.wav')
            out.update(audio=base64.b64encode(open(p, 'rb').read()).decode(), mime='audio/wav')
        except Exception as e:
            out['tts_error'] = str(e)
        return out
    return await asyncio.to_thread(work)

''' + anchor, 1)

# ---------- UI: glasses-mode toggle under the talk button ----------
ui = 'Hold, speak, release &mdash; Chinnu answers out loud</div></div>'
assert ui in m
m = m.replace(ui, 'Hold, speak, release &mdash; Chinnu answers out loud</div>'
              '<button id="glb" onclick="glToggle()" style="width:100%;margin-top:8px;font-size:14px"></button></div>', 1)

js_anchor = '// phone push-to-talk (needs https -> tailscale link)'
assert js_anchor in m
m = m.replace(js_anchor, r'''// glasses mode: tap once, talk; Chinnu's answer plays on the phone (-> Bluetooth glasses); keeps listening for follow-ups
let GL=false;try{GL=localStorage.getItem('glasses')==='1'}catch(e){}
const AU=new Audio();AU.playsInline=true;let conv=false;
function glUI(){const b=$('glb');if(!b)return;b.innerHTML=GL?'&#127911; Glasses mode ON &mdash; tap once &amp; talk, answer plays in your glasses':'&#127911; Glasses / phone-speaker mode: off';b.style.background=GL?'#1d5a3a':'';
 $('ptt').innerHTML=GL?'&#127897; Tap to talk (glasses)':'&#127897; Hold to talk (phone mic)';$('pttmsg').textContent=GL?'Tap, speak - Chinnu answers in your glasses and keeps listening. Tap again to stop.':'Hold, speak, release - Chinnu answers out loud'}
function glToggle(){GL=!GL;try{localStorage.setItem('glasses',GL?'1':'0')}catch(e){};glUI()}
async function listenOnce(){
 const st=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
 const mt=MediaRecorder.isTypeSupported('audio/webm')?'audio/webm':'audio/mp4';
 const r=new MediaRecorder(st,{mimeType:mt});const ch=[];r.ondataavailable=x=>ch.push(x.data);
 const ac=new (window.AudioContext||window.webkitAudioContext)();const an=ac.createAnalyser();an.fftSize=1024;ac.createMediaStreamSource(st).connect(an);const buf=new Uint8Array(an.fftSize);
 let spoke=false,last=Date.now();const t0=Date.now();const done=new Promise(res=>{r.onstop=res});
 r.start();$('ptt').style.background='var(--bad)';$('pttmsg').textContent='listening...';
 while(r.state==='recording'){await new Promise(z=>setTimeout(z,100));an.getByteTimeDomainData(buf);let mx=0;for(const v of buf)mx=Math.max(mx,Math.abs(v-128));
  if(mx>14){spoke=true;last=Date.now()}const now=Date.now();
  if(!conv||(spoke&&now-last>1300)||(!spoke&&now-t0>7000)||now-t0>20000)r.stop()}
 await done;st.getTracks().forEach(t=>t.stop());try{ac.close()}catch(e){};$('ptt').style.background='';
 if(!spoke||!conv)return false;
 $('pttmsg').textContent='thinking...';
 try{const x=await (await fetch('/api/voice_reply',{method:'POST',headers:{'Content-Type':mt},body:new Blob(ch,{type:mt})})).json();
  if(!x.text){$('pttmsg').textContent='(nothing heard)';return false}
  $('pttmsg').textContent='\u{1F5E3} '+x.text+'  \u{1F436} '+(x.reply||'');
  if(x.audio){AU.src='data:'+x.mime+';base64,'+x.audio;await AU.play().catch(()=>{});await new Promise(z=>{AU.onended=z;AU.onerror=z;setTimeout(z,90000)})}
  return true}catch(e){$('pttmsg').textContent='failed';return false}}
async function glTap(e){if(e)e.preventDefault();if(conv){conv=false;return}
 conv=true;AU.src='data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=';AU.play().catch(()=>{});
 try{while(conv&&await listenOnce()){}}catch(err){$('pttmsg').textContent='mic blocked: open the https tailscale link'}
 conv=false;$('ptt').style.background=''}
''' + js_anchor, 1)

a = 'async function pttStart(e){e.preventDefault();if(rec)return;'
assert a in m
m = m.replace(a, 'async function pttStart(e){if(GL)return glTap(e);e.preventDefault();if(rec)return;', 1)
b = 'function pttStop(){'
assert b in m
m = m.replace(b, 'function pttStop(){if(GL)return;', 1)
c = "setInterval(netg,30000);netg();"
assert c in m
m = m.replace(c, c + "glUI();", 1)
open(P, 'w', encoding='utf-8').write(m)
print('patched')
