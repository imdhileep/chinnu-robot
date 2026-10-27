"""Chinnu's own voice (offline): Tinglish -> Telugu script (Chinnu's own small transliteration model in Ollama)
-> VITS voice fine-tuned on Chinnu's voice -> 16 kHz WAV. Used by speech_server.py /tts."""
import io, os, re, json, threading, requests, numpy as np, soundfile as sf, torch
from transformers import VitsModel, AutoTokenizer

HERE = os.path.dirname(os.path.abspath(__file__))
VOICE = os.path.join(HERE, 'models/chinnu-voice-tel')
XLIT_MODEL = 'chinnu-xlit'
OLLAMA = 'http://127.0.0.1:11434'
model = VitsModel.from_pretrained(VOICE).eval()
tok = AutoTokenizer.from_pretrained(VOICE)
VOCAB = set(json.load(open(os.path.join(VOICE, 'vocab.json'))))
SR = model.config.sampling_rate
_lock = threading.Lock()
torch.set_num_threads(4)

from xlit import to_telugu      # Tinglish -> Telugu script (dictionary learned from Chinnu's sentences)

def _clean(t):
    t = t.replace('‌', '').replace('‍', '')
    t = ''.join(ch if (ch in VOCAB or ch == ' ') else ' ' for ch in t)
    return ' '.join(t.split())

def synth(text):
    te = to_telugu(text)
    parts = [p for p in re.split(r'(?<=[.!?।])\s+|[\n,;:]\s*', te) if p.strip()] or [te]
    gap = np.zeros(int(0.12 * SR), dtype='float32')
    out = []
    with _lock, torch.no_grad():
        for p in parts:
            c = _clean(p)
            if len(c) < 2: continue
            x = tok(c, return_tensors='pt')
            w = model(**x).waveform[0].numpy().astype('float32')
            out += [w, gap]
    audio = np.concatenate(out) if out else np.zeros(int(0.2 * SR), dtype='float32')
    audio = audio / max(1e-3, float(np.abs(audio).max())) * 0.9
    buf = io.BytesIO(); sf.write(buf, audio, SR, format='WAV', subtype='PCM_16')
    return buf.getvalue()
