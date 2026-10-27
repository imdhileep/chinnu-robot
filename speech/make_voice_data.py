"""Chinnu voice dataset: Chinnu-style replies -> natural Telugu script (GPT-4.1-mini) -> audio in Chinnu's CURRENT voice
(gpt-4o-mini-tts 'echo' + child instructions + sox pitch +600, exactly like voice.py). Run on the server (has the key + sox).
Usage: python make_voice_data.py replies.json outdir N"""
import sys, os, json, subprocess, concurrent.futures as cf
from openai import OpenAI
c = OpenAI()
SRC, OUT, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
os.makedirs(f'{OUT}/wavs', exist_ok=True)
CHILD = ('Speak like an adorable, cheerful little 4-year-old child - a bright, high-pitched, playful, giggly small voice, '
         'full of excitement and wonder. Clear, natural Telugu; warm and sweet; no animal noises or sound effects.')
lines = json.load(open(SRC))[:N]

def to_telugu(batch):
    msg = ('Convert each line to natural Telugu script exactly as it would be spoken aloud (Tinglish -> Telugu letters; '
           'English words written phonetically in Telugu script, e.g. light -> లైట్, TV -> టీవీ; numbers as Telugu words). '
           'Keep the meaning and words; no translation of style. Return JSON {"out": [..same order..]}.\n' + json.dumps(batch, ensure_ascii=False))
    r = c.chat.completions.create(model='gpt-4.1-mini', temperature=0, response_format={'type': 'json_object'},
                                  messages=[{'role': 'user', 'content': msg}])
    out = json.loads(r.choices[0].message.content).get('out', [])
    return list(zip(batch, out)) if len(out) == len(batch) else []

pairs = []
with cf.ThreadPoolExecutor(6) as ex:
    for res in ex.map(to_telugu, [lines[i:i + 20] for i in range(0, len(lines), 20)]):
        pairs += res
json.dump([{'src': a, 'te': b} for a, b in pairs], open(f'{OUT}/xlit_pairs.json', 'w'), ensure_ascii=False, indent=0)

def speak(i_pair):
    i, (src, te) = i_pair
    raw, wav = f'/tmp/cv_{i}.wav', f'{OUT}/wavs/c{i:04d}.wav'
    try:
        r = c.audio.speech.create(model='gpt-4o-mini-tts', voice='echo', input=te, response_format='wav', instructions=CHILD)
        r.write_to_file(raw)
        subprocess.run(['sox', raw, '-r', '16000', '-c', '1', wav, 'norm', '-1', 'pitch', '600', 'silence', '1', '0.05', '0.5%', 'reverse',
                        'silence', '1', '0.05', '0.5%', 'reverse'], check=True, capture_output=True)
        os.remove(raw)
        return {'file': f'c{i:04d}.wav', 'text': te, 'src': src}
    except Exception as e:
        print('fail', i, e, flush=True); return None

meta = []
with cf.ThreadPoolExecutor(6) as ex:
    for k, m in enumerate(ex.map(speak, enumerate(pairs))):
        if m: meta.append(m)
        if k % 100 == 0: print(k, flush=True)
json.dump(meta, open(f'{OUT}/metadata.json', 'w'), ensure_ascii=False, indent=0)
print('clips', len(meta))
