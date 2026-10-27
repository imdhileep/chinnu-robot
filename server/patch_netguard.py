import shutil
B = '/home/dk/chinnu-agent/'
for f in ('dashboard.py', 'mobile.py'): shutil.copy(B + f, B + f + '.bak_netguard')

d = open(B + 'dashboard.py').read()
e = "    import nightly; nightly.start()\n"
assert e in d
d = d.replace(e, e + "    import netguard; netguard.start()\n", 1)
d += """

@app.get('/api/netguard')
def api_netguard():
    import netguard; return netguard.status()
"""
open(B + 'dashboard.py', 'w').write(d)

m = open(B + 'mobile.py').read()
top = '<div id="top"><h1>Chinnu</h1><span class="dot" id="dot"></span><span id="st">...</span></div>'
assert top in m
m = m.replace(top, top + '\n<div id="netban" style="display:none;margin:8px 12px 0;padding:10px 12px;border-radius:12px;background:#7a1d1d;color:#fff;font-size:14px;font-weight:600"></div>', 1)
js = "setInterval(poll,2000);poll();"
assert js in m
m = m.replace(js, """async function netg(){try{const r=await (await fetch('/api/netguard')).json();const b=document.getElementById('netban');
 if(r.ok){b.style.display='none';return}
 b.textContent='\\u26a0\\ufe0f Server internet down since '+r.down_since+' ('+r.down_min+' min). '+(r.cable?'Trying to fix automatically\\u2026':'Ethernet cable unplugged \\u2014 check the cable!');b.style.display='block'}catch(e){}}
setInterval(netg,30000);netg();
""" + js, 1)
open(B + 'mobile.py', 'w').write(m)
print('patched')
