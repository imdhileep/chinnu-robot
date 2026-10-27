"""Step A: generate diverse things Chintu might say to Chinnu (user turns only).
Usage: python gen_prompts.py <scale>   (scale 1.0 = full set ~1200, 0.05 = pilot)"""
import os, sys, json, random, concurrent.futures as cf
from openai import OpenAI

client = OpenAI()
SCALE = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
OUT = sys.argv[2] if len(sys.argv) > 2 else 'data/prompts.jsonl'

STYLE = ("Chintu is a young Telugu software engineer in Kansas talking to Chinnu, his robot dog, by VOICE. "
         "Mix styles: ~45% Tinglish (Telugu in English letters, e.g. 'light off cheyyi ra'), ~35% Telugu script "
         "(e.g. 'రూమ్ లైట్ ఆఫ్ చెయ్యి'), ~20% casual English. Add some speech-to-text noise: missing words, "
         "wrong spellings, 'chinnu' sometimes misheard as 'chinna'/'chinnamma'. Vary length (2-25 words), mood, slang "
         "(bro, ra, mama, anna, basu). Never number the lines.")

from v2_cats import CATS

def batch(cat, desc, n):
    msg = (f"{STYLE}\nCategory: {desc}.\nWrite {n} different things Chintu says. "
           'Return JSON: {"lines": ["...", ...]}')
    r = client.chat.completions.create(model='gpt-4.1-mini', temperature=1.0, response_format={'type': 'json_object'},
                                       messages=[{'role': 'user', 'content': msg}])
    return [(cat, l.strip()) for l in json.loads(r.choices[0].message.content).get('lines', []) if l.strip()]

jobs = []
for cat, (n, desc) in CATS.items():
    n = max(2, round(n * SCALE))
    while n > 0:
        k = min(30, n); jobs.append((cat, desc, k)); n -= k

out, seen = [], set()
with cf.ThreadPoolExecutor(8) as ex:
    for res in ex.map(lambda j: batch(*j), jobs):
        for cat, l in res:
            if l.lower() not in seen: seen.add(l.lower()); out.append({'cat': cat, 'text': l})

# real things Chintu said (from Chinnu's logs), deduped
if False:
    real = json.load(open('data/real_user.json'))
    random.seed(1); random.shuffle(real)
    for l in real[:max(5, round(400 * SCALE))]:
        if l.lower() not in seen: seen.add(l.lower()); out.append({'cat': 'real', 'text': l})

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w') as f:
    for o in out: f.write(json.dumps(o, ensure_ascii=False) + '\n')
print(len(out), 'prompts ->', OUT)
