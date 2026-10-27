"""Compare speech-to-text options on the 12 known Telugu clips: character error rate (lower = better) + speed."""
import json, time, sys, numpy as np, soundfile as sf, jiwer, torch
from scipy.signal import resample_poly
from math import gcd
T = json.load(open('test/truth.json'))

def load(f):
    a, sr = sf.read(f, dtype='float32')
    if a.ndim > 1: a = a.mean(1)
    if sr != 16000:
        g = gcd(sr, 16000); a = resample_poly(a, 16000 // g, sr // g).astype('float32')
    return a

def norm(s): return ''.join(ch for ch in s.lower() if ch.isalnum() or 'ఀ' <= ch <= '౿')

def report(name, hyps, secs):
    cer = jiwer.cer([norm(t['text']) for t in T], [norm(h) for h in hyps])
    print(f'{name:38s} CER {cer:.2f}  avg {np.mean(secs):.2f}s')
    for t, h in list(zip(T, hyps))[:12]: print('    ', t['text'][:34].ljust(34), '->', h.strip()[:60])

report('gpt-4o-transcribe (OpenAI, current)', [t['gpt'] for t in T], [0])

import mlx_whisper
for repo in ['mlx-community/whisper-large-v3-turbo', 'mlx-community/whisper-large-v3-mlx']:
    hyps, secs = [], []
    for t in T:
        s = time.time(); hyps.append(mlx_whisper.transcribe(load('test/' + t['file']), path_or_hf_repo=repo, language='te')['text']); secs.append(time.time() - s)
    report(repo.split('/')[-1], hyps, secs[1:])

from transformers import pipeline
for repo in sys.argv[1:]:
    pipe = pipeline('automatic-speech-recognition', model=repo, device='mps', torch_dtype=torch.float16)
    hyps, secs = [], []
    for t in T:
        s = time.time()
        hyps.append(pipe(load('test/' + t['file']), generate_kwargs={'language': 'telugu', 'task': 'transcribe'})['text']); secs.append(time.time() - s)
    report(repo.split('/')[-1], hyps, secs[1:])
