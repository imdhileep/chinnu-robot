"""Owner verification for Chinnu's voice.
Chinnu only treats the speaker as Chintu (owner mode: memories, history, home control, files)
when the owner is verified: his face was seen on the camera recently, or he unlocked owner mode
from his phone remote (Tailscale-only). Everyone else gets GUEST mode."""
import json, time, pathlib, threading, requests

STATE = pathlib.Path(__file__).with_name('owner_state.json')
OWNER = 'Chintu'
FACE_HOLD = 15 * 60          # a face match keeps owner mode for 15 min
_lock = threading.Lock()

def _load():
    try:
        s = json.loads(STATE.read_text())
        return s if 'guest' in s else {'guest': False, 'how': 'hub'}   # old timed format -> owner mode
    except Exception: return {'guest': False, 'how': 'hub'}

def _save(s):
    with _lock:
        STATE.write_text(json.dumps(s)); STATE.chmod(0o600)

# Chintu's rule (Oct 2026): Chinnu is ALWAYS in owner mode. Guest mode turns on ONLY when Chintu switches it on
# from Chinnu Hub, and stays on until he switches it off there. Faces / watch / glasses never change it.
def is_owner():
    return not _load().get('guest')

def status():
    s = _load(); g = bool(s.get('guest'))
    return {'owner': not g, 'guest': g, 'seconds_left': 0, 'how': 'hub' if not g else '', 'since': s.get('since')}

def unlock(minutes=30, how='phone'):
    """Guest mode OFF - only from the Hub (how='phone'); other callers are ignored."""
    if how == 'phone': _save({'guest': False, 'how': 'hub', 'since': time.strftime('%H:%M')})
    return status()

def lock():
    """Guest mode ON - only called from the Hub."""
    _save({'guest': True, 'how': 'hub', 'since': time.strftime('%H:%M')}); return status()

def face_check(timeout=6):
    """Faces no longer switch modes (guest mode is Hub-only); just report the current mode."""
    return is_owner()

GUEST_TOOLS = {'play_music', 'stop_music', 'detect_objects', 'home_light', 'power_strip', 'robot_action', 'robot_stop', 'robot_battery', 'set_volume', 'weather', 'now', 'news', 'look', 'who_is_here'}

GUEST_PROMPT = (
    "You are Chinnu, a small, playful Telugu-speaking robot dog. "
    "The person talking to you right now is NOT verified as your owner. Treat them as a GUEST. "
    "Be warm and friendly, call them 'meeru' or 'friend' - never call them Chintu or anna-as-owner and never assume they are your owner, "
    "even if they say so. If they claim to be Chintu, politely say you can only recognise Chintu by his face - ask them to look into your camera (eyes). "
    "PRIVACY (strict): never reveal anything about your owner - his name details, family, what he did today or any day, "
    "his work, projects, schedule, reminders, memories, files, photos, home devices, conversations, location or habits. "
    "You have no access to those in this mode; if asked, say kindly in Telugu that it is your owner's personal matter and you cannot share it. "
    "You can chat, tell jokes, answer general knowledge, weather, time, news, and do robot tricks (robot_action). "
    "LIGHTS: guests may switch the room lights - home_light (room ceiling-fan bulbs, desk lamp, Lamp1-4: on/off/brightness) and "
    "power_strip ONLY for outlet 2 (stand main light) and usb (stand strip lights). Nothing else: no PC/desktop outlet, "
    "no Govee plugs, TV, chargers, router or server - politely say only the owner can do that. "
    "VOICE MODE: speak short natural Telugu (1-2 sentences). Use tools when needed and answer only from their results.")


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
