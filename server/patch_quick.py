v = open('voice_agent.py', encoding='utf-8').read()
if 'QUICK_ACK' not in v:
    old = "chat_lock = threading.Lock()\n"
    new = '''chat_lock = threading.Lock()

# ---- instant spoken ack while the brain is still composing the reply (commands feel snappy) ----
QUICK_ACK = {'robot_action': 'Sare anna!', 'home_light': 'Sare anna!', 'set_volume': 'Sare!', 'run_command': 'Sare anna!',
             'home_camera': 'Oka nimisham, chustha.', 'look': 'Chustha anna.', 'who_is_here': 'Chustha.', 'news': 'Oka nimisham.', 'weather': 'Chustha.'}
_ACK_FILES = {}
def _quick_ack_file(text):
    p = _ACK_FILES.get(text)
    if not p:
        p = f'/tmp/chinnu_qack_{abs(hash(text)) % 100000}.wav'
        if not os.path.exists(p):
            try: voice.tts(text, p)
            except Exception as e: print('[qack tts]', e, flush=True); return None
        _ACK_FILES[text] = p
    return p

_orig_run_tool = brain.run_tool
def _run_tool_with_ack(name, args):
    text = QUICK_ACK.get(name)
    if text and V.get('quick_ack', True):
        p = _quick_ack_file(text)
        if p: threading.Thread(target=say_file, args=(p,), daemon=True).start()
    return _orig_run_tool(name, args)
brain.run_tool = _run_tool_with_ack
'''
    assert old in v; v = v.replace(old, new, 1)
    open('voice_agent.py', 'w', encoding='utf-8').write(v); print('voice_agent ok')

c = open('config.yaml', encoding='utf-8-sig').read()
c2 = c.replace('  silence_rms: 6.0', '  silence_rms: 4.5', 1)
if 'quick_ack' not in c2:
    c2 = c2.replace("  ack: chime", "  ack: chime\n  quick_ack: true     # say 'Sare anna!' instantly when a command tool runs", 1)
if c2 != c:
    open('config.yaml', 'w', encoding='utf-8').write(c2); print('config ok')
