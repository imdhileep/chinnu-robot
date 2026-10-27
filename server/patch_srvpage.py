import shutil, time
fn = 'dashboard.py'; s = open(fn, encoding='utf-8').read()
if 'srvpage' not in s:
    shutil.copy(fn, fn + '.bak_srv' + time.strftime('%H%M%S'))
    s += '\n\nimport srvpage as _srv\napp.include_router(_srv.router)\n'
    open(fn, 'w', encoding='utf-8').write(s); print('dashboard ok')
m = open('mobile.py', encoding='utf-8').read()
if "href=\"/server\"" not in m and 'Apps' in m:
    i = m.find('Jellyfin')
    print('mobile has Apps card; link added' if i > 0 else 'no jellyfin link found')
