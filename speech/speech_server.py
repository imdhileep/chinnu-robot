"""Chinnu speech server on the Mac (127.0.0.1:8091, reached by the Chinnu server through the ssh tunnel as 127.0.0.1:11436).
/stt  : WAV bytes -> Telugu text (Whisper large-v2 fine-tuned for Telugu, converted to MLX)
/tts  : text -> WAV in Chinnu's own voice (added once the voice model is trained)
/health"""
import io, os, time, threading, numpy as np, soundfile as sf
from math import gcd
from scipy.signal import resample_poly
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
import mlx_whisper

HERE = os.path.dirname(os.path.abspath(__file__))
STT_MODEL = os.path.join(HERE, 'models/whisper-telugu-large-v2-mlx')
app = FastAPI(title='Chinnu speech')
_lock = threading.Lock()          # MLX: one transcription at a time
stats = {'stt': 0, 'stt_secs': 0.0, 'tts': 0}

def _audio(b):
    a, sr = sf.read(io.BytesIO(b), dtype='float32')
    if a.ndim > 1: a = a.mean(1)
    if sr != 16000:
        g = gcd(sr, 16000); a = resample_poly(a, 16000 // g, sr // g).astype('float32')
    return a

@app.post('/stt')
async def stt(req: Request):
    b = await req.body()
    t = time.time()
    with _lock:
        text = mlx_whisper.transcribe(_audio(b), path_or_hf_repo=STT_MODEL, language='te',
                                      condition_on_previous_text=False)['text'].strip()
    stats['stt'] += 1; stats['stt_secs'] += time.time() - t
    return {'text': text, 'secs': round(time.time() - t, 2)}

TTS = None   # set by tts_engine when the voice model exists
try:
    import tts_engine; TTS = tts_engine
except Exception as e:
    print('[speech] no TTS yet:', e, flush=True)

@app.post('/tts')
async def tts(req: Request):
    if TTS is None: return JSONResponse({'error': 'voice model not installed'}, status_code=503)
    d = await req.json()
    wav = TTS.synth(d.get('text', ''))
    stats['tts'] += 1
    return Response(wav, media_type='audio/wav')

@app.get('/health')
def health():
    return {'ok': True, 'stt_ready': True, 'tts_ready': TTS is not None, **stats}

# warm the model so the first real request is fast
threading.Thread(target=lambda: mlx_whisper.transcribe(np.zeros(16000, dtype='float32'), path_or_hf_repo=STT_MODEL, language='te'), daemon=True).start()
