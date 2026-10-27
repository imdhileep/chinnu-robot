import shutil, time
c = open('config.yaml', encoding='utf-8').read()
if '\nhome_auto:' not in c:
    c += '''
home_auto:             # home_auto.py
  owner_macs: []       # Chintu's phone Wi-Fi MAC(s) -> auto home/away
  away_min: 10         # phone off Wi-Fi this long -> "leaving home"
  quiet_start: "23:00" # quiet hours: no proactive talking, low volume
  quiet_end: "07:00"
  quiet_volume: 20
  day_volume: 70
  briefing_at: "07:00" # morning briefing on Telegram
  diary_at: "22:05"    # Chinnu diary on Telegram
  door_alerts: true    # Blink motion -> Telegram photo + "door daggara evaro unnaru"
'''
    open('config.yaml', 'w', encoding='utf-8').write(c); print('config ok')
s = open('dashboard.py', encoding='utf-8').read()
if 'home_auto' not in s:
    shutil.copy('dashboard.py', 'dashboard.py.bak_home' + time.strftime('%H%M%S'))
    s += '''
if not os.environ.get('CHINNU_LAN'):
    import home_auto; home_auto.start(ROBOT, HDR)

@app.get('/api/home_auto')
def api_home_auto():
    import home_auto; return home_auto.status()

@app.get('/api/home_auto/briefing')
def api_briefing(send: int = 0):
    import home_auto; t = home_auto.briefing_text()
    if send: home_auto.tg(t)
    return {'text': t}
'''
    open('dashboard.py', 'w', encoding='utf-8').write(s); print('dashboard ok')
# guard mode / door alerts / reminders: no talking during quiet hours
b = open('behaviors.py', encoding='utf-8').read()
if 'quiet_now' not in b:
    b = b.replace("def _say(text):\n", "def _say(text):\n    try:\n        import home_auto\n        if home_auto.quiet_now(): return\n    except Exception: pass\n", 1)
    open('behaviors.py', 'w', encoding='utf-8').write(b); print('behaviors ok')
