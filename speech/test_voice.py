"""Objective voice check: speak test sentences with a voice model, transcribe them with the Telugu Whisper, measure CER.
Usage: python test_voice.py <model_dir or checkpoint dir> [base_dir_for_config]"""
import sys, os, json, io, numpy as np, soundfile as sf, torch, jiwer, mlx_whisper
from transformers import VitsModel, AutoTokenizer, VitsConfig
from scipy.signal import resample_poly
from xlit import to_telugu
path = sys.argv[1]; base = sys.argv[2] if len(sys.argv) > 2 else path
cfg = VitsConfig.from_pretrained(base); tok = AutoTokenizer.from_pretrained(base)
model = VitsModel.from_pretrained(path, config=cfg).eval() if (not os.path.isdir(path) or os.path.exists(os.path.join(path, 'config.json'))) else None
if model is None:
    from safetensors.torch import load_file
    model = VitsModel(cfg).eval(); sd = load_file(os.path.join(path, 'model.safetensors'))
    missing, unexpected = model.load_state_dict(sd, strict=False); print('missing', len(missing), 'unexpected', len(unexpected))
vocab = set(tok.get_vocab())
S = ['Hai anna! Nenu Chinnu, nee robot dog.', 'Room light off chesanu anna, inka em kavali?', 'Ippudu time 9:32 AM anna.',
     'Battery 93% undi, full power lo unna!', 'Sorry anna, adi cheyalekapoyanu.', 'Good night anna, sweet dreams!',
     'Anna, main door daggara evaro unnaru.', 'Naatu Naatu paata pedutunna, dance cheddama?']
refs, hyps = [], []
os.makedirs('/tmp/voice_test', exist_ok=True)
for i, s in enumerate(S):
    te = to_telugu(s); clean = ' '.join(''.join(c if c in vocab or c == ' ' else ' ' for c in te).split())
    with torch.no_grad(): w = model(**tok(clean, return_tensors='pt')).waveform[0].numpy()
    sf.write(f'/tmp/voice_test/v{i}.wav', w, cfg.sampling_rate)
    a = resample_poly(w, 16000, cfg.sampling_rate).astype('float32') if cfg.sampling_rate != 16000 else w.astype('float32')
    h = mlx_whisper.transcribe(a, path_or_hf_repo='models/whisper-telugu-large-v2-mlx', language='te')['text']
    refs.append(clean); hyps.append(h); print(f'{len(w)/cfg.sampling_rate:4.1f}s | {clean[:40]:40s} -> {h[:50]}')
norm = lambda s: ''.join(ch for ch in s if 'ఀ' <= ch <= '౿')
print('CER', round(jiwer.cer([norm(r) for r in refs], [norm(h) for h in hyps]), 3))
