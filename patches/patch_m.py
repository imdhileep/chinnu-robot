import re
p = 'mobile.py'; s = open(p, encoding='utf-8').read()
tabs = open('app_tabs.html', encoding='utf-8').read()
wifi = open('app_wifi.html', encoding='utf-8').read()
js = open('app_js.js', encoding='utf-8').read()

a = s.index('<section class="tab" id="t-server">'); b = s.index('</main>', a)
s = s[:a] + tabs + '<div id="dog" style="display:none"></div><div id="svcs" style="display:none"></div>\n' + s[b:]

old_nav = s[s.index('<nav>'):s.index('</nav>') + 6]
nav = ('<nav><button class="on" onclick="tab(\'home\',this)"><span>&#128054;</span>Chinnu</button>'
       '<button onclick="tab(\'ctl\',this)"><span>&#127918;</span>Control</button>'
       '<button onclick="tab(\'lights\',this)"><span>&#127968;</span>Home</button>'
       '<button onclick="tab(\'server\',this)"><span>&#128200;</span>Status</button>'
       '<button onclick="tab(\'alerts\',this)"><span>&#128276;</span>Alerts</button></nav>')
s = s.replace(old_nav, nav)

r = ' <div class="card"><h3>Routines</h3>'
assert s.count(r) == 1; s = s.replace(r, wifi + r)

k = 'setInterval(poll,2000);poll();'
assert s.count(k) == 1; s = s.replace(k, js + '\n' + k)

t = '<meta name="apple-mobile-web-app-capable" content="yes">'
if 'apple-mobile-web-app-title' not in s:
    s = s.replace(t, t + '<meta name="apple-mobile-web-app-title" content="Chinnu">', 1)
open(p, 'w', encoding='utf-8').write(s); print('mobile patched')
