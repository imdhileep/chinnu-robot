import shutil, time
ts = time.strftime('%H%M%S')
def patch(fn, pairs):
    s = open(fn, encoding='utf-8').read(); shutil.copy(fn, f'{fn}.bak_gl{ts}')
    for a, b in pairs:
        assert s.count(a) == 1, (fn, a[:60]); s = s.replace(a, b)
    open(fn, 'w', encoding='utf-8').write(s); print('patched', fn)

patch('owner.py', [
("GUEST_TOOLS = {'robot_action',", "GUEST_TOOLS = {'home_light', 'power_strip', 'robot_action',"),
("    \"You cannot control lights, plugs or home devices for guests. \"",
 "    \"LIGHTS: guests may switch the room lights - home_light (room ceiling-fan bulbs, desk lamp, Lamp1-4: on/off/brightness) and \"\n"
 "    \"power_strip ONLY for outlet 2 (stand main light) and usb (stand strip lights). Nothing else: no PC/desktop outlet, \"\n"
 "    \"no Govee plugs, TV, chargers, router or server - politely say only the owner can do that. \""),
])
s = open('owner.py', encoding='utf-8').read()
if 'def guest_allowed' not in s:
    s += '''

_LIGHT_OUTLETS = ('2', 'usb', 'stand main light', 'main light', 'strip light', 'stand strip', 'usb ports')
def guest_allowed(name, args):
    """Per-call guard for guest mode (tools list alone is not enough for multi-device tools)."""
    if name not in GUEST_TOOLS: return False
    if name == 'power_strip':
        if (args.get('action') or '') == 'status': return True
        o = str(args.get('outlet', '')).strip().lower()
        return any(o == k or k in o for k in _LIGHT_OUTLETS) and not any(b in o for b in ('all', '3', 'desktop', 'pc', 'power box', 'powerbox'))
    if name == 'home_light':
        return (args.get('action') or '') in ('on', 'off', 'brightness', 'list')
    return True
'''
    open('owner.py', 'w', encoding='utf-8').write(s)

patch('realtime.py', [
("                        if _mode != 'owner' and name not in owner.GUEST_TOOLS:\n",
 "                        if _mode != 'owner' and not owner.guest_allowed(name, a):\n"),
])
