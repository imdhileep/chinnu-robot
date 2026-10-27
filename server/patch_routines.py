import shutil, time, re
ts = time.strftime('%H%M%S')
fn = 'commands.py'
s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_rt' + ts)
if "kind == 'plug'" not in s:
    a = "        if kind == 'sleep':"
    assert s.count(a) == 1
    s = s.replace(a, '''        if kind == 'plug' and len(parts) >= 3:     # plug <govee socket / group, may have spaces> on|off
            import govee_plug
            return govee_plug.set_plug(' '.join(parts[1:-1]), parts[-1].lower() == 'on')
        if kind == 'strip' and len(parts) >= 3:    # strip <1|2|3|usb|friendly name> on|off
            import tuya_strip
            return tuya_strip.set_outlet(' '.join(parts[1:-1]), parts[-1].lower() == 'on')
''' + a)
    open(fn, 'w', encoding='utf-8').write(s); print('commands.py patched')

fn = 'commands.yaml'
shutil.copy(fn, fn + '.bak_rt' + ts)
new = '''# Chinnu custom commands. Edit freely; Chinnu reloads this file on every call.
# Each command: say (optional reply), steps (list), shell (optional fixed shell command on the server).
# Step formats:
#   light <name> on|off|brightness <1-100>   (name: room | desk | all | Lamp1..Lamp4)
#   lights on|off|brightness <n>          (all lamps)
#   plug <govee socket or group> on|off   (google tv | tv screen | tv | wireless charger | pidog charger ...)
#                                          chinnu server / modem / router are protected and never switched off
#   strip <1|2|3|usb> on|off              (2 = stand main light, usb = stand strip lights + clock, 3 = desktop PC)
#   robot <sit|stand|lie|wag_tail|tilt_head|shake_head|stretch|forward|backward|turn_left|turn_right>
#   volume <0-100> | volume mute|unmute
#   sleep <seconds>
#   speak <text>                        (Chinnu says this out loud)
#   brain <prompt>                      (ask the brain, tools allowed, and speak the reply)
# Schedules: add  schedule: "07:00"  (or  schedule: {at: "07:00", days: [mon,tue,wed,thu,fri], enabled: true})
#   -> the command runs at that time every day; its 'say' text is spoken.

# ---- Routines ----
good morning:
  description: "Morning routine (scheduled weekdays 7:00): lights, weather + news"
  schedule: {at: "07:00", days: [mon, tue, wed, thu, fri], enabled: true}
  say: "Good morning anna! Lechi ready avvu, roju start cheddam."
  steps:
    - light room brightness 40
    - strip 2 on
    - robot stand
    - robot wag_tail
    - brain Good morning anna. Ivala Overland Park weather (temperature, rain) oka line lo cheppu, tharuvatha top 3 news headlines (india or world) chinna ga cheppu. Telugu lo, 4-5 short sentences, cheerful ga.

movie mode:
  description: "TV on, lights dim, stand lights off"
  say: "Sare anna, movie mode on. Enjoy!"
  steps:
    - plug tv on
    - lights brightness 15
    - strip 2 off
    - strip usb off
    - volume 25
    - robot lie

movie off:
  description: "TV off, lights back to normal"
  say: "Movie ayipoyindi anna, lights on chesa."
  steps:
    - plug tv off
    - light room brightness 70

work mode:
  description: "Full light, stand lights on"
  say: "Work mode anna, full focus."
  steps:
    - lights brightness 100
    - strip 2 on
    - strip usb on
    - volume 50
    - robot sit

good night:
  description: "Everything off except the server/internet; Chinnu keeps charging by itself"
  say: "Good night anna, nenu guard duty lo untanu."
  steps:
    - plug tv off
    - lights off
    - strip 2 off
    - strip usb off
    - volume 20
    - robot lie

leaving home:
  description: "Going out: lights and TV off"
  say: "Sare anna, jagratha! Lights, TV off chesa. Nenu illu chusukuntanu."
  steps:
    - plug tv off
    - lights off
    - strip 2 off
    - strip usb off
    - robot sit

im home:
  description: "Back home: lights on, Chinnu says hi"
  say: "Welcome back anna! Miss ayya."
  steps:
    - light room brightness 70
    - strip 2 on
    - robot stand
    - robot wag_tail

# ---- Status ----
server status:
  say: "Server status chustunna anna."
  shell: "uptime -p; echo temp $(vcgencmd measure_temp); df -h / | awk 'NR==2{print \\"disk\\", $5, \\"used\\"}'; free -h | awk 'NR==2{print \\"ram\\", $3, \\"/\\", $2}'"

pidog battery:
  shell: "curl -s -m 5 -H \\"x-token: $CHINNU_TOKEN\\" http://192.168.1.208:8090/status"

# ---- Light presets (room = 3 fan bulbs, desk = stand lamp) ----
morning light:
  say: "Morning light on anna."
  steps:
    - light room brightness 40

full light:
  say: "Full brightness anna."
  steps:
    - light room brightness 100

mood light:
  say: "Mood light set chesa anna."
  steps:
    - light room brightness 15

room light on:
  steps:
    - light room on

room light off:
  steps:
    - light room off

desk lamp on:
  steps:
    - light desk on

desk lamp off:
  steps:
    - light desk off
'''
open(fn, 'w', encoding='utf-8').write(new); print('commands.yaml rewritten')
import yaml; d = yaml.safe_load(open(fn, encoding='utf-8')); print(len(d), 'commands:', ', '.join(d))
