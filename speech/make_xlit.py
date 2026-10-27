"""More Tinglish -> Telugu-script pairs (for Chinnu's own transliteration model). Run on the server (has the key)."""
import json, sys, concurrent.futures as cf
from openai import OpenAI
c = OpenAI()
lines = json.load(open(sys.argv[1]))
def conv(batch):
    msg = ('Convert each line to natural Telugu script exactly as it would be spoken aloud (Tinglish -> Telugu letters; '
           'English words written phonetically in Telugu script, e.g. light -> లైట్, TV -> టీవీ; numbers as Telugu words; '
           'lines already in Telugu script stay as they are). Keep the words; do not translate. '
           'Return JSON {"out": [..same order..]}.\n' + json.dumps(batch, ensure_ascii=False))
    r = c.chat.completions.create(model='gpt-4.1-mini', temperature=0, response_format={'type': 'json_object'},
                                  messages=[{'role': 'user', 'content': msg}])
    out = json.loads(r.choices[0].message.content).get('out', [])
    return [{'src': a, 'te': b} for a, b in zip(batch, out)] if len(out) == len(batch) else []
pairs = []
with cf.ThreadPoolExecutor(8) as ex:
    for res in ex.map(conv, [lines[i:i + 20] for i in range(0, len(lines), 20)]): pairs += res
json.dump(pairs, open(sys.argv[2], 'w'), ensure_ascii=False)
print(len(pairs))
