"""Step C: clean teacher data -> mlx-lm chat files (train/valid) + held-out test set.
Each example with tool calls becomes 2 samples (ends at the tool call / ends at the final reply),
because mlx-lm (mask_prompt) trains only the last assistant turn."""
import json, re, random
from student_prompt import STUDENT_SYSTEM

rows = [json.loads(l) for l in open('data/teacher.jsonl')]
BAD_SCRIPT = re.compile(r'[ಀ-೿ऀ-ॿ؀-ۿ஀-௿]')
stats = {'in': len(rows), 'long': 0, 'noisy': 0, 'script': 0, 'empty': 0}

def keep(r):
    m = r['messages']; user = m[0]['content']; final = m[-1].get('content') or ''
    if not final.strip(): stats['empty'] += 1; return False
    if len(final.split()) > 40 or '\n\n' in final: stats['long'] += 1; return False
    if BAD_SCRIPT.search(final): stats['script'] += 1; return False
    called = any(x.get('tool_calls') for x in m)
    if r['cat'] == 'real' and called and len(user.split()) <= 2: stats['noisy'] += 1; return False
    return True

def to_openai(m):
    out = []
    for x in m:
        if x['role'] == 'assistant' and x.get('tool_calls'):
            out.append({'role': 'assistant', 'content': '', 'tool_calls': [
                {'type': 'function', 'function': {'name': c['name'], 'arguments': c['arguments']}} for c in x['tool_calls']]})
        elif x['role'] == 'tool':
            out.append({'role': 'tool', 'content': x['content']})
        else:
            out.append({'role': x['role'], 'content': x['content']})
    return out

good = [r for r in rows if keep(r)]
random.seed(42); random.shuffle(good)
n_test = 100; n_valid = 60
test, valid, train = good[:n_test], good[n_test:n_test + n_valid], good[n_test + n_valid:]

def samples(r):
    msgs = [{'role': 'system', 'content': STUDENT_SYSTEM}] + to_openai(r['messages'])
    cuts = [i for i, x in enumerate(msgs) if x['role'] == 'assistant']
    return [{'messages': msgs[:i + 1]} for i in cuts]

for name, part in (('train', train), ('valid', valid)):
    with open(f'data/mlx/{name}.jsonl', 'w') as f:
        k = 0
        for r in part:
            for s in samples(r): f.write(json.dumps(s, ensure_ascii=False) + '\n'); k += 1
    print(name, len(part), 'examples ->', k, 'samples')
with open('data/test.jsonl', 'w') as f:
    for r in test: f.write(json.dumps(r, ensure_ascii=False) + '\n')
print('test', len(test)); print(stats, 'kept', len(good))
