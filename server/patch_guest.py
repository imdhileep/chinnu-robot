import shutil, re
B = '/home/dk/chinnu-agent/'
for f in ('owner.py', 'mobile.py'): shutil.copy(B + f, B + f + '.bak_guest')

o = open(B + 'owner.py').read()
start = o.index('def _load():'); end = o.index('GUEST_TOOLS')
o = o[:start] + '''def _load():
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

'''  + o[end:]
open(B + 'owner.py', 'w').write(o)

m = open(B + 'mobile.py').read()
# header badge
old = """$('own').textContent=r.owner?('\\u{1F513} owner '+Math.ceil(r.seconds_left/60)+'m ('+r.how+')'):'\\u{1F512} guest'"""
assert old in m, 'ownGet'
m = m.replace(old, """$('own').textContent=r.owner?'\\u{1F513} owner':'\\u{1F512} GUEST mode ON'""", 1)
# buttons
i = m.index('onclick="ownSet(\'unlock\')">'); j = m.index('</button>', i)
m = m[:i] + 'onclick="ownSet(\'unlock\')">&#128275; Its me (guest off)' + m[j:]
k = m.index('onclick="ownSet(\'lock\')">'); l = m.index('</button>', k)
m = m[:k] + 'onclick="ownSet(\'lock\')">&#128274; Guest mode ON' + m[l:]
# modes card
old2 = "m.owner?Math.ceil((m.owner_left||0)/60)+' min left':'guest rules now'"
assert old2 in m, 'modes'
m = m.replace(old2, "m.owner?'always on - guest only from Hub':'GUEST rules now'", 1)
open(B + 'mobile.py', 'w').write(m)
print('patched')
