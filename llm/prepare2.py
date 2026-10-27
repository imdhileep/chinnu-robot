"""v2 data: v1 teacher data + targeted v2 data. The 100 v1 test questions stay held out (same test = fair compare)."""
import json, random, re, os
from student_prompt import STUDENT_SYSTEM
import prepare as P            # reuses keep() / to_openai() / samples(); runs v1 split as a side effect (harmless)

test_users = {json.loads(l)['messages'][0]['content'] for l in open('data/test.jsonl')}
rows = [json.loads(l) for l in open('data/teacher.jsonl')] + [json.loads(l) for l in open('data/teacher_v2.jsonl')]
REPEAT = re.compile(r'(\b\w+\b)(\s+\1\b){4,}', re.I)
def keep2(r):
    called = any(m.get('tool_calls') for m in r['messages'])
    if r['cat'] in ('unknown_device', 'tools_general') and called: return False
    return not any(REPEAT.search(m.get('content') or '') for m in r['messages'] if m['role'] == 'assistant')
good = [r for r in rows if r['messages'][0]['content'] not in test_users and P.keep(r) and keep2(r)]
random.seed(43); random.shuffle(good)
valid, train = good[:70], good[70:]
os.makedirs('data/mlx2', exist_ok=True)
for name, part in (('train', train), ('valid', valid)):
    k = 0
    with open(f'data/mlx2/{name}.jsonl', 'w') as f:
        for r in part:
            msgs = [{'role': 'system', 'content': STUDENT_SYSTEM}] + P.to_openai(r['messages'])
            for i, x in enumerate(msgs):
                if x['role'] == 'assistant':
                    f.write(json.dumps({'messages': msgs[:i + 1]}, ensure_ascii=False) + '\n'); k += 1
    print(name, len(part), 'examples ->', k, 'samples')
from collections import Counter
print(Counter(r['cat'] for r in train).most_common())
