"""Chinnu-LLM: Chintu's own fine-tuned model (Qwen2.5-3B + LoRA, trained on the Mac), served by Ollama on this server.
Full brain: Tinglish replies + real tool calls (<tool_call>{json}</tool_call>), no OpenAI needed.
Mode switch: brain_mode.json {"mode": "gpt" | "chinnu"}  (app Status tab / voice 'my model mode')."""
import os, re, json, time, requests

HERE = os.path.dirname(os.path.abspath(__file__))
URL = 'http://127.0.0.1:11434'
MODEL = 'chinnu:3b'
MODE_FILE = os.path.join(HERE, 'brain_mode.json')
CALL = re.compile(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', re.S)
history = []          # [(user, reply)] last few turns, owner only
stats = {'calls': 0, 'secs': 0.0, 'last': None, 'errors': 0}

from student_prompt import STUDENT_SYSTEM

def mode():
    try: return json.load(open(MODE_FILE)).get('mode', 'gpt')
    except Exception: return 'gpt'

def set_mode(m):
    json.dump({'mode': m, 'at': time.strftime('%Y-%m-%d %H:%M:%S')}, open(MODE_FILE, 'w'))
    return m

# (label, url, models in order of preference). Mac's Ollama is reached through an ssh tunnel when the Mac is on;
# the Pi prefers the smaller 1.5B model (about 2x faster there).
BACKENDS = [('Mac (fast)', 'http://127.0.0.1:11435', ['chinnu:3b']), ('Pi', URL, ['chinnu:1.5b', 'chinnu:3b'])]
_pick = {'t': 0, 'name': None, 'url': None, 'model': None}

def _has_model(url, wanted, timeout):
    try:
        names = [t.get('name', '') for t in requests.get(f'{url}/api/tags', timeout=timeout).json().get('models', [])]
        return next((w for w in wanted if any(n == w or n == w + ':latest' for n in names)), None)
    except Exception:
        return None

def backend(force=False):
    """(name, url) of the fastest backend that has a Chinnu model; re-checked every 20 s."""
    if force or time.time() - _pick['t'] > 20:
        _pick.update(t=time.time(), name=None, url=None, model=None)
        for name, url, wanted in BACKENDS:
            m = _has_model(url, wanted, 1.0 if 'Mac' in name else 3)
            if m:
                _pick.update(name=f'{name} · {m}', url=url, model=m); break
    return _pick['name'], _pick['url']

def available(timeout=3):
    return backend()[1] is not None

def _im(role, text): return f'<|im_start|>{role}\n{text}<|im_end|>\n'

def _render(turns):
    """turns: list of (role, text) where role in system/user/assistant. Mirrors Qwen2.5's chat template."""
    return ''.join(_im(r, t) for r, t in turns) + '<|im_start|>assistant\n'

def _gen(prompt, n=160):
    body = {'prompt': prompt, 'raw': True, 'stream': False, 'keep_alive': '24h',
            'options': {'temperature': 0.3, 'top_p': 0.9, 'num_predict': n, 'num_ctx': 2048, 'stop': ['<|im_end|>', '<|im_start|>']}}
    name, url = backend()
    for attempt in (0, 1):
        body['model'] = _pick.get('model') or MODEL
        body['keep_alive'] = '24h' if 'Mac' in (name or '') else '10m'   # Pi RAM is small: free it after 10 idle minutes
        try:
            r = requests.post(f'{url}/api/generate', json=body, timeout=120 if 'Pi' in (name or '') else 30)
            r.raise_for_status()
            stats['backend'] = name
            return (r.json().get('response') or '').strip()
        except Exception:
            if attempt: raise
            name, url = backend(force=True)          # Mac went to sleep -> fall back to the Pi
            if not url: raise

VALID = {'robot_action', 'robot_stop', 'robot_battery', 'home_light', 'govee_plug', 'power_strip', 'set_volume', 'run_command',
         'list_commands', 'play_music', 'stop_music', 'look', 'detect_objects', 'who_is_here', 'camera', 'home_camera', 'enroll_face',
         'guard_mode', 'follow_me', 'saver_mode', 'wifi_speed', 'remember', 'forget', 'set_reminder', 'list_reminders',
         'cancel_reminder', 'weather', 'now', 'news', 'nextcloud_search'}
PROTECTED_WORDS = re.compile(r'modem|router|server|internet|wi-?fi|\bnet\b|మోడెమ్|రౌటర్|సర్వర్|ఇంటర్నెట్', re.I)

def _guard(user_text, name, args):
    """Hard safety rules the small model can't override. Returns an error dict to block, else None."""
    if name not in VALID:
        return {'ok': False, 'error': f'no tool called {name} - I cannot do that'}
    act = str(args.get('action', '')).lower()
    if name in ('govee_plug', 'power_strip') and act == 'off':
        if PROTECTED_WORDS.search(user_text) or any(p in str(args.get('target', '')).lower() for p in ('server', 'modem', 'router')):
            return {'ok': False, 'error': 'chinnu server, modem and router are protected - never switched off'}
        if name == 'power_strip' and str(args.get('outlet', '')).lower() in ('3', 'all', 'desktop', 'pc'):
            return {'ok': False, 'error': 'desktop PC outlet: Chintu must switch it off himself from the app'}
    return None

def _allowed(name, args):
    try:
        import owner
        if owner.is_owner(): return True
        return name in owner.GUEST_TOOLS and owner.guest_allowed(name, args)
    except Exception:
        return True

def chat(text, on_tool=None):
    import brain
    t0 = time.time()
    try:
        import owner; is_owner = owner.is_owner()
    except Exception: is_owner = True
    turns = [('system', STUDENT_SYSTEM)]
    if is_owner:
        for u, a in history[-3:]: turns += [('user', u), ('assistant', a)]
    turns.append(('user', text))
    reply = ''
    for _ in range(3):
        out = _gen(_render(turns))
        calls = CALL.findall(out)
        if not calls:
            reply = CALL.sub('', out).strip(); break
        results = []
        for js in calls:
            try: c = json.loads(js)
            except Exception: results.append({'ok': False, 'error': 'bad tool json'}); continue
            name, args = c.get('name', ''), c.get('arguments') or {}
            blocked = _guard(text, name, args)
            if blocked:
                res = blocked
            elif not _allowed(name, args):
                res = {'ok': False, 'error': 'guest mode: not allowed'}
            else:
                try: res = brain.run_tool(name, args)
                except Exception as e: res = {'ok': False, 'error': str(e)[:120]}
            print(f'  [chinnu-llm] {name}({args}) -> {str(res)[:120]}', flush=True)
            if on_tool: on_tool(name, args, res)
            results.append(res)
        turns.append(('assistant', out.strip()))
        turns.append(('user', '\n'.join('<tool_response>\n' + json.dumps(r, ensure_ascii=False, default=str)[:600] + '\n</tool_response>' for r in results)))
    reply = reply or 'Sare anna!'
    if is_owner:
        history.append((text, reply)); del history[:-6]
    stats['calls'] += 1; stats['secs'] += time.time() - t0; stats['last'] = round(time.time() - t0, 1)
    return reply

def status():
    return {'mode': mode(), 'model': MODEL, 'available': available(), 'backend': backend()[0], 'calls': stats['calls'],
            'avg_secs': round(stats['secs'] / stats['calls'], 1) if stats['calls'] else None, 'last_secs': stats['last']}
