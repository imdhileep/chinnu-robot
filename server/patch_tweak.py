p = 'mobile.py'; s = open(p, encoding='utf-8').read()
a = """+'</div><div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted)"><span>24h ago</span><span>now</span></div>'}"""
assert s.count(a) == 1; s = s.replace(a, "+'</div>'}")
b = """(m.charging?'charging':'not charging')+(m.battery!=null?' · '+m.battery+'%':'')"""
assert s.count(b) == 1; s = s.replace(b, "(m.charging?'charging':'not charging')")
c = """const GROUPS={"""
s = s.replace(c, "const GROUPS_NOTE='Bars = last 24 h (green up, red down)';" + c, 1)
d = """h+='<div class="card"><h3>'+gl+' <span"""
s = s.replace(d, """h+='<div class="card"><h3>'+gl+(g==='core'?' <span style="text-transform:none;letter-spacing:0;font-size:11px">· bars = last 24 h</span>':'')+' <span""", 1)
open(p, 'w', encoding='utf-8').write(s); print('ok')
