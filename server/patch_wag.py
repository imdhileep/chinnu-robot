import shutil
B = '/home/dk/chinnu-agent/'
for f in ('voice_agent.py', 'brain.py', 'commands.yaml'): shutil.copy(B + f, B + f + '.bak_wag')

v = open(B + 'voice_agent.py').read()
a = "pick = random.choice(['look', 'look', 'look', 'tilt_head', 'shake_head', 'wag_tail'])"
assert a in v
v = v.replace(a, "pick = random.choice(['look', 'look', 'look', 'tilt_head', 'shake_head'])   # no wag when idle (Chintu: too much wagging)")
b = "                try: robot.action('wag_tail')\n                except Exception: pass\n                voice.say(msg)"
assert b in v
v = v.replace(b, "                voice.say(msg)   # greeting without tail wag (Chintu: too much wagging)")
open(B + 'voice_agent.py', 'w').write(v)

br = open(B + 'brain.py').read()
c = '"You can also do a small reaction action on your own when it fits the emotion (wag_tail when happy, "\n    "tilt_head when curious), but never when Chintu says to stay still."'
assert c in br
br = br.replace(c, '"You may RARELY do a small reaction on your own (tilt_head when curious). Do NOT wag_tail on your own - only when Chintu asks for it. "\n    "Never move when Chintu says to stay still."')
open(B + 'brain.py', 'w').write(br)

y = open(B + 'commands.yaml').read()
d = '  description: "Phone back on Wi-Fi: guard mode off, Chinnu says hi"\n  say: "Welcome back anna! Miss ayya."\n  steps:\n    - guard off\n    - robot wag_tail\n'
assert d in y
y = y.replace(d, '  description: "Phone back on Wi-Fi: guard mode off, Chinnu says hi"\n  say: "Welcome back anna! Miss ayya."\n  steps:\n    - guard off\n')
open(B + 'commands.yaml', 'w').write(y)
print('patched')
