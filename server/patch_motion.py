import shutil
B = '/home/dk/chinnu-agent/'
for f in ('dashboard.py', 'mobile.py'): shutil.copy(B + f, B + f + '.bak_motion')

d = open(B + 'dashboard.py').read()
e = "    import home_auto; home_auto.start(ROBOT, HDR)\n"
assert e in d
d = d.replace(e, e + "    import motioncam; motioncam.start(ROBOT, HDR)\n", 1)
d += """

@app.get('/api/motion')
def api_motion():
    import motioncam; return motioncam.status()

@app.post('/api/motion/{act}')
def api_motion_set(act: str):
    import motioncam
    if act in ('on', 'off'): return motioncam.set_cfg(on=(act == 'on'))
    if act in ('away', 'always', 'never'): return motioncam.set_cfg(telegram='off' if act == 'never' else act)
    return {'ok': False}

@app.get('/api/motion/recent')
def api_motion_recent(n: int = 12):
    import motioncam; return {'items': motioncam.recent(min(n, 60))}

@app.get('/api/motion/img/{day}/{file}')
def api_motion_img(day: str, file: str):
    import motioncam
    from fastapi.responses import Response
    b = motioncam.image(day, file)
    return Response(b, media_type='image/jpeg') if b else Response(status_code=404)
"""
open(B + 'dashboard.py', 'w').write(d)

m = open(B + 'mobile.py', encoding='utf-8').read()
a = '<section class="tab" id="t-alerts">\n'
assert a in m
m = m.replace(a, a + ''' <div class="card"><h3>&#128248; Motion photos <span id="mstat" style="float:right;text-transform:none;letter-spacing:0;font-size:12px"></span></h3>
  <div style="font-size:13px;color:var(--muted);margin-bottom:8px">Chinnu takes a photo whenever its camera sees movement. Saved to the hard disk + Nextcloud (30 days).</div>
  <div class="row"><button id="mon" onclick="motionSet(MS.on?'off':'on')">...</button></div>
  <div style="font-size:12px;color:var(--muted);margin:8px 0 4px">Send to Telegram:</div>
  <div class="row" style="gap:4px"><button id="mt-away" onclick="motionSet('away')">When I'm away</button><button id="mt-always" onclick="motionSet('always')">Always</button><button id="mt-off" onclick="motionSet('never')">Never</button></div>
  <div id="mgrid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px"></div></div>
''', 1)
js = 'async function alerts(){'
assert js in m
m = m.replace(js, r'''let MS={};async function motionLoad(){try{MS=await (await fetch('/api/motion')).json();
 $('mstat').textContent=(MS.on?'ON':'off')+' · '+MS.today+' today'+(MS.last_photo?' · last '+MS.last_photo:'');
 $('mon').textContent=MS.on?'\u{1F4F8} Motion photos ON (tap to turn off)':'Motion photos OFF (tap to turn on)';$('mon').style.background=MS.on?'#1d5a3a':'';
 ['away','always','off'].forEach(k=>{$('mt-'+k).style.background=(MS.telegram===k)?'var(--accent)':'';$('mt-'+k).style.color=(MS.telegram===k)?'#000':''});
 const r=await (await fetch('/api/motion/recent?n=12')).json();
 $('mgrid').innerHTML=r.items.length?r.items.map(x=>'<a href="/api/motion/img/'+x.day+'/'+x.file+'" target="_blank" style="text-decoration:none"><img loading="lazy" src="/api/motion/img/'+x.day+'/'+x.file+'" style="width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:8px"><div style="font-size:11px;color:var(--muted);text-align:center">'+x.day.slice(5)+' '+x.t+'</div></a>').join(''):'<div style="grid-column:1/-1;color:var(--muted);font-size:13px">No motion photos yet.</div>'}catch(e){}}
async function motionSet(a){await post('/api/motion/'+a);motionLoad()}
async function alerts(){motionLoad();''', 1)
open(B + 'mobile.py', 'w', encoding='utf-8').write(m)
print('patched')
