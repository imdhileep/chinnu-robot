"""Local LLM (Ollama on chinnu-server) - fallback brain when OpenAI is unreachable.
Commands go through a deterministic keyword router (never guessed by the small model);
the model is used only for short chit-chat."""
import re, requests, yaml, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = (yaml.safe_load(open(os.path.join(HERE, 'config.yaml'), encoding='utf-8-sig')) or {}).get('local_llm', {}) or {}
URL = CFG.get('url', 'http://127.0.0.1:11434')
MODEL = CFG.get('model', 'qwen2.5:3b')
SYSTEM = ("You are Chinnu, a small friendly robot dog who lives with Chintu. Reply in ONE short sentence, "
          "in simple Telugu written in English letters, warm and playful. Never claim you did any action.")
history = []

ON = r'\b(on|pettu|veyyi|start)\b'
OFF = r'\b(off|aapu|aapey|teeseyyi|stop)\b'
ROUTES = [  # (pattern, tool, args)
    (r'stand (main )?light|stand lamp', 'power_strip', {'outlet': '2'}),
    (r'strip light|usb', 'power_strip', {'outlet': 'usb'}),
    (r'desk (light|lamp)', 'home_light', {'name': 'desk'}),
    (r'room light|fan light|ceiling', 'home_light', {'name': 'room'}),
    (r'\bfan\b', 'govee_plug', {'target': 'fan'}),
    (r'all lights|anni lights', 'home_light', {'name': 'all'}),
]
ACTIONS = {r'kurcho|\bsit\b': 'sit', r'nilabadu|nilapadu|stand up': 'stand', r'paduko|\blie\b': 'lie',
           r'tail|wag': 'wag_tail', r'stretch': 'stretch'}

def available(timeout=2):
    try: return requests.get(f'{URL}/api/version', timeout=timeout).ok
    except Exception: return False

def route(text):
    """Return (tool, args) for an obvious command, else None."""
    t = text.lower()
    on, off = re.search(ON, t), re.search(OFF, t)
    if on or off:
        for pat, tool, args in ROUTES:
            if re.search(pat, t):
                return tool, {**args, 'action': 'on' if on and not off else 'off'}
    for pat, name in ACTIONS.items():
        if re.search(pat, t) and 'light' not in t:
            return 'robot_action', {'name': name}
    if re.search(r'\btime\b|samayam|ganta', t): return 'now', {}
    if re.search(r'weather|vaatavaranam|varsham|\brain\b', t): return 'weather', {}
    return None

def chat(text):
    try:
        import chinnu_llm
        if chinnu_llm.available(): return chinnu_llm.chat(text)
    except Exception as e:
        print('[local] chinnu-llm failed', e, flush=True)
    import brain
    r = route(text)
    if r:
        tool, args = r
        res = brain.run_tool(tool, args)
        print(f'  [local route] {tool}({args}) -> {str(res)[:120]}', flush=True)
        if tool == 'now':
            return f"Ippudu time {time.strftime('%I:%M %p')} anna."
        if tool == 'weather' and isinstance(res, dict) and res.get('ok'):
            return f"Ippudu {round(res.get('now_f', 0))} degrees, {res.get('sky', '')} anna."
        ok = isinstance(res, dict) and res.get('ok', True) is not False
        return 'Sare anna, chesanu!' if ok else 'Sorry anna, adi cheyalekapoyanu.'
    history.append({'role': 'user', 'content': text}); del history[:-6]
    rr = requests.post(f'{URL}/api/chat', json={'model': MODEL, 'stream': False,
                       'messages': [{'role': 'system', 'content': SYSTEM}] + history,
                       'options': {'temperature': 0.7, 'num_predict': 50}}, timeout=60)
    out = ((rr.json().get('message') or {}).get('content') or '').strip() or 'Hmm anna?'
    history.append({'role': 'assistant', 'content': out})
    return out
