import shutil, time
fn = 'dashboard.py'
s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_ac' + time.strftime('%H%M%S'))
if 'autocharge' not in s:
    a = "if not os.environ.get('CHINNU_LAN'): threading.Thread(target=_robot_poll, daemon=True).start()"
    assert s.count(a) == 1
    s = s.replace(a, a + "\nif not os.environ.get('CHINNU_LAN'):\n    import autocharge; autocharge.start(ROBOT, HDR)")
    s += '''

@app.get('/api/autocharge')
def api_autocharge():
    import autocharge; return autocharge.status()
'''
    open(fn, 'w', encoding='utf-8').write(s); print('dashboard patched')
c = open('config.yaml', encoding='utf-8').read()
if 'autocharge:' not in c:
    c += '''
autocharge:            # Govee 'pidog charger' socket switched by battery voltage (autocharge.py)
  enabled: true
  low_v: 7.3           # charger ON below this (~39%)
  full_v: 8.3          # charger OFF at/above this on 2 readings in a row (~94%)
  max_hours: 5         # safety: never charge longer than this
  offline_min: 6       # robot unreachable this long -> charger ON (flat battery)
  every_s: 120
'''
    open('config.yaml', 'w', encoding='utf-8').write(c); print('config patched')
