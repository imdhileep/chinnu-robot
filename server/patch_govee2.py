c = open('config.yaml', encoding='utf-8-sig').read()
i = c.index('govee:'); j = c.index('local_llm:')
c = c[:i] + '''govee:                 # Govee dual smart plugs (cloud API)
  sockets:
    Misev:
      1: chinnu server
      2: pidog charger
    Spectrum WiFi:
      1: modem
      2: router
    TV:
      1: google tv
      2: tv screen
    Dual Smart Plug:
      1: wireless charger
      2: empty
  locked: [chinnu server, modem, router]     # never switched OFF by Chinnu
  groups:
    tv: [google tv, tv screen]
    chargers: [pidog charger, wireless charger]

''' + c[j:]
open('config.yaml', 'w', encoding='utf-8').write(c)

b = open('brain.py', encoding='utf-8').read()
old = '". Use the friendly socket names when Chintu names the appliance. POWER STRIP'
new = '". Groups: tv = google tv + tv screen, chargers = pidog charger + wireless charger. chinnu server, modem and router are PROTECTED and can never be switched off - never try. Use the friendly socket/group names when Chintu names the appliance. POWER STRIP'
if 'PROTECTED' not in b:
    assert old in b; b = b.replace(old, new, 1)
    open('brain.py', 'w', encoding='utf-8').write(b)
print('ok')
