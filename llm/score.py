"""Score results/*.jsonl: tool accuracy (vs teacher), reply length, + optional LLM judge (needs OPENAI_API_KEY).
Usage: python score.py results/a.jsonl [results/b.jsonl ...] [--judge]"""
import sys, json, re, statistics as st, concurrent.futures as cf
files = [a for a in sys.argv[1:] if not a.startswith('--')]
JUDGE = '--judge' in sys.argv
TE = re.compile(r'[ఀ-౿]')

def names(calls): return sorted({c.get('name') for c in calls})

def key_args(c):
    a = c.get('arguments') or {}
    return {k: str(v).lower() for k, v in a.items() if k in ('name', 'action', 'target', 'outlet', 'camera', 'percent')}

def judge(r):
    from openai import OpenAI
    msg = ("Rate the robot dog Chinnu's turn from 1 (bad) to 5 (excellent). Chinnu must: do the right tool action for the request "
           "(or none for chat), reply in casual Telugu/Tinglish like a funny loyal dog to his owner Chintu, be 1-2 short sentences, "
           "be honest (no claimed actions without tool calls), make sense.\n"
           f"Chintu said: {r['user']}\nChinnu's tool calls: {json.dumps(r['calls'], ensure_ascii=False)}\nChinnu replied: {r['reply']}\n"
           f"(Reference from a strong model - calls: {json.dumps(r['gold_calls'], ensure_ascii=False)}, reply: {r['gold_reply']})\n"
           'Return JSON {"score": n, "why": "short"}')
    out = OpenAI().chat.completions.create(model='gpt-4.1-mini', temperature=0, response_format={'type': 'json_object'},
                                           messages=[{'role': 'user', 'content': msg}]).choices[0].message.content
    return json.loads(out)

for fn in files:
    rows = [json.loads(l) for l in open(fn)]
    tool_rows = [r for r in rows if r['gold_calls']]
    chat_rows = [r for r in rows if not r['gold_calls']]
    exact = sum(names(r['calls']) == names(r['gold_calls']) for r in tool_rows)
    argok = sum(names(r['calls']) == names(r['gold_calls']) and
                sorted(json.dumps(key_args(c), sort_keys=True) for c in r['calls']) == sorted(json.dumps(key_args(c), sort_keys=True) for c in r['gold_calls'])
                for r in tool_rows)
    false_calls = sum(bool(r['calls']) for r in chat_rows)
    bad_json = sum(any(c.get('name') == 'BAD_JSON' for c in r['calls']) for r in rows)
    words = [len(r['reply'].split()) for r in rows]
    res = {'file': fn, 'n': len(rows),
           'tool_right': f'{exact}/{len(tool_rows)}', 'tool+args_right': f'{argok}/{len(tool_rows)}',
           'chat_wrongly_called_tool': f'{false_calls}/{len(chat_rows)}', 'bad_json': bad_json,
           'reply_words_median': st.median(words), 'replies_over_40_words': sum(w > 40 for w in words),
           'secs_median': st.median(r.get('secs', 0) for r in rows)}
    if JUDGE:
        with cf.ThreadPoolExecutor(8) as ex: js = list(ex.map(judge, rows))
        for r, j in zip(rows, js): r['judge'] = j
        res['judge_avg'] = round(st.mean(j['score'] for j in js), 2)
        res['judge_by_cat'] = {c: round(st.mean(j['score'] for r, j in zip(rows, js) if r['cat'] == c), 2) for c in sorted({r['cat'] for r in rows})}
        json.dump(rows, open(fn.replace('.jsonl', '_judged.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))
