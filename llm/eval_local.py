"""Step E: run a model (base or base+adapter) on the held-out test set with the real tool loop (mock results).
Usage: python eval_local.py <name> [adapter_path]  -> results/<name>.jsonl"""
import sys, json, re, time, os
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler
from student_prompt import STUDENT_SYSTEM
sys.argv += [None] * 2
NAME, ADAPTER = sys.argv[1], sys.argv[2]
import importlib.util
spec = importlib.util.spec_from_file_location('mockmod', 'mock_tools.py'); mm = importlib.util.module_from_spec(spec); spec.loader.exec_module(mm)

model, tok = load(os.environ.get('BASE', 'models/qwen2.5-3b-instruct'), adapter_path=ADAPTER)
sampler = make_sampler(temp=0.3)
CALL = re.compile(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', re.S)

def ask(msgs):
    p = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    return generate(model, tok, prompt=p, max_tokens=160, sampler=sampler).strip()

def run(user):
    msgs = [{'role': 'system', 'content': STUDENT_SYSTEM}, {'role': 'user', 'content': user}]
    calls, t0 = [], time.time()
    for _ in range(3):
        out = ask(msgs)
        found = CALL.findall(out)
        if not found:
            return {'calls': calls, 'reply': out.replace('<|im_end|>', '').strip(), 'secs': round(time.time() - t0, 2)}
        tcs = []
        for js in found:
            try: c = json.loads(js)
            except Exception: c = {'name': 'BAD_JSON', 'arguments': {}}
            calls.append(c); tcs.append(c)
        msgs.append({'role': 'assistant', 'content': '', 'tool_calls': [{'type': 'function', 'function': {'name': c.get('name'), 'arguments': c.get('arguments', {})}} for c in tcs]})
        for c in tcs:
            msgs.append({'role': 'tool', 'content': json.dumps(mm.mock(c.get('name'), c.get('arguments') or {}), ensure_ascii=False)})
    return {'calls': calls, 'reply': '(too many tool rounds)', 'secs': round(time.time() - t0, 2)}

os.makedirs('results', exist_ok=True)
tests = [json.loads(l) for l in open(os.environ.get('TESTS', 'data/test.jsonl'))]
with open(f'results/{NAME}.jsonl', 'w') as f:
    for i, t in enumerate(tests):
        user = t['messages'][0]['content']
        gold_calls = [c for m in t['messages'] if m.get('tool_calls') for c in m['tool_calls']]
        r = run(user)
        f.write(json.dumps({'cat': t['cat'], 'user': user, 'gold_calls': gold_calls, 'gold_reply': t['messages'][-1]['content'], **r}, ensure_ascii=False) + '\n')
        if i % 20 == 0: print(NAME, i, flush=True)
print('done', NAME)
