"""Step B: the teacher (gpt-4.1 with Chinnu's real persona + tools) answers every prompt.
Tool calls get realistic fake results so the full turn (call -> result -> reply) is recorded.
Usage: python teacher.py data/prompts.jsonl data/teacher.jsonl [model]"""
import sys, json, random, time, threading, concurrent.futures as cf
from openai import OpenAI

client = OpenAI()
SRC, OUT = sys.argv[1], sys.argv[2]
MODEL = sys.argv[3] if len(sys.argv) > 3 else 'gpt-4.1'
D = json.load(open('data/chinnu_tools.json'))
SYSTEM, TOOLS = D['system'], D['tools']
PROTECTED = ('server', 'modem', 'router')
R = random.Random(7)

def mock(name, a):
    t = time.strftime('%I:%M %p')
    if name == 'govee_plug':
        tg = str(a.get('target', '')).lower()
        if a.get('action') == 'off' and any(p in tg for p in PROTECTED):
            return {'ok': False, 'refused': [tg], 'error': f'{tg} is protected and can never be switched off'}
        if a.get('action') in ('status', 'list'): return {'ok': True, 'state': {tg or 'tv': R.choice([True, False])}}
        return {'ok': True, 'target': tg, 'on': a.get('action') == 'on'}
    if name == 'power_strip':
        if str(a.get('outlet')) == '3' and a.get('action') == 'off':
            return {'ok': False, 'error': 'outlet 3 is the desktop PC - ask Chintu to confirm first'}
        return {'ok': True, 'outlet': a.get('outlet'), 'on': a.get('action') == 'on'}
    if name == 'home_light': return {'ok': R.random() > 0.05, **a}
    if name == 'set_volume': return {'ok': True, 'volume': a.get('percent') or R.choice([40, 50, 60, 70, 80])}
    if name == 'robot_action': return {'ok': True, 'done': a.get('name')}
    if name == 'robot_stop': return {'ok': True}
    if name == 'robot_battery':
        p = R.randint(15, 98); return {'percent': p, 'voltage': round(6.8 + p * 0.016, 2), 'charging': R.random() < 0.3}
    if name == 'now': return {'time': t, 'date': time.strftime('%A, %d %B %Y')}
    if name == 'weather':
        return {'ok': True, 'now_f': R.randint(38, 88), 'sky': R.choice(['clear', 'cloudy', 'light rain', 'sunny', 'windy']),
                'high_f': R.randint(55, 92), 'low_f': R.randint(30, 60), 'rain_chance': R.choice([0, 10, 40, 80])}
    if name == 'news':
        return {'ok': True, 'headlines': ['India beat Australia in the 2nd T20', 'New AI chip announced for laptops',
                                          'Heavy rains expected in coastal Andhra this week']}
    if name in ('remember', 'forget'): return {'ok': True}
    if name == 'set_reminder': return {'ok': True, 'id': R.randint(1, 40), 'when': a.get('at') or f"in {a.get('minutes')} min"}
    if name == 'list_reminders': return {'reminders': [{'id': 3, 'text': 'call amma', 'when': '8:00 PM'}]}
    if name == 'cancel_reminder': return {'ok': True}
    if name == 'play_music': return {'ok': True, 'playing': a.get('query', 'song'), 'source': 'youtube'}
    if name == 'stop_music': return {'ok': True, 'was_playing': True}
    if name == 'look':
        return {'ok': True, 'answer': R.choice(['Chintu sitting at the desk with a laptop', 'a person holding a coffee mug',
                                                'an empty room with a sofa and a TV', 'Chintu holding a phone and smiling'])}
    if name == 'who_is_here': return {'ok': True, 'people': R.choice([['Chintu'], [], ['unknown person'], ['Chintu', 'unknown person']]), 'voice': 'Chintu'}
    if name == 'detect_objects': return {'ok': True, 'objects': R.choice([['person', 'laptop', 'cup'], ['chair', 'tv', 'bottle'], ['person', 'cell phone']])}
    if name == 'home_camera': return {'ok': True, 'answer': R.choice(['nobody at the door, a parcel on the mat', 'empty patio, it is dark', 'a delivery person at the door'])}
    if name == 'camera': return {'ok': True, 'action': a.get('action'), 'saved': 'Chinnu/gallery'}
    if name == 'enroll_face': return {'ok': True, 'name': a.get('name')}
    if name in ('guard_mode', 'follow_me', 'saver_mode'): return {'ok': True, 'on': a.get('action') == 'on'}
    if name == 'wifi_speed': return {'ok': True, 'device': a.get('device'), 'limit_mbps': a.get('mbps')}
    if name == 'run_command': return {'ok': True, 'ran': a.get('name')}
    if name == 'list_commands': return {'commands': ['good morning', 'movie mode', 'movie off', 'work mode', 'good night', 'leaving home', 'im home']}
    if name == 'nextcloud_search': return {'ok': True, 'files': [f"Chinnu/gallery/{a.get('query', 'photo')}_01.jpg"]}
    return {'ok': True}

def run(p):
    msgs = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': p['text']}]
    rec = [{'role': 'user', 'content': p['text']}]
    for _ in range(4):
        for attempt in range(4):
            try:
                r = client.chat.completions.create(model=MODEL, messages=msgs, tools=TOOLS, temperature=0.8, max_tokens=300)
                break
            except Exception as e:
                time.sleep(3 * (attempt + 1)); err = e
        else:
            return None
        if r.usage:
            with lock:
                U['in'] += r.usage.prompt_tokens; U['out'] += r.usage.completion_tokens
                U['cached'] += getattr(r.usage.prompt_tokens_details, 'cached_tokens', 0) or 0
        m = r.choices[0].message
        if m.tool_calls:
            calls = [{'name': c.function.name, 'arguments': json.loads(c.function.arguments or '{}')} for c in m.tool_calls]
            msgs.append({'role': 'assistant', 'content': m.content, 'tool_calls': [c.model_dump() for c in m.tool_calls]})
            rec.append({'role': 'assistant', 'tool_calls': calls})
            for c, tc in zip(calls, m.tool_calls):
                res = json.dumps(mock(c['name'], c['arguments']), ensure_ascii=False)
                msgs.append({'role': 'tool', 'tool_call_id': tc.id, 'content': res})
                rec.append({'role': 'tool', 'name': c['name'], 'content': res})
            continue
        rec.append({'role': 'assistant', 'content': (m.content or '').strip()})
        return {'cat': p['cat'], 'messages': rec, 'usage': r.usage.model_dump() if r.usage else None}
    return None

prompts = [json.loads(l) for l in open(SRC)]
lock, n = threading.Lock(), 0
U = {'in': 0, 'cached': 0, 'out': 0}
with open(OUT, 'w') as f, cf.ThreadPoolExecutor(8) as ex:
    for res in ex.map(run, prompts):
        if not res: continue
        with lock:
            f.write(json.dumps(res, ensure_ascii=False) + '\n'); n += 1
            if n % 50 == 0: print(n, 'done', flush=True)
P = {'gpt-4.1': (2.0, 0.5, 8.0), 'gpt-4.1-mini': (0.4, 0.1, 1.6)}.get(MODEL, (2.0, 0.5, 8.0))
cost = ((U['in'] - U['cached']) * P[0] + U['cached'] * P[1] + U['out'] * P[2]) / 1e6
print(n, 'examples ->', OUT, '| tokens', U, f'| cost ~${cost:.2f}')
