"""Voice (speaker) verification for Chinnu - wespeaker ResNet34 via sherpa-onnx, fully local.
enroll(name, wav) adds a voice sample; verify(wav) -> (name|None, score)."""
import io, json, wave, pathlib, threading
import numpy as np
import sherpa_onnx

DIR = pathlib.Path(__file__).parent
DB = DIR / 'voices.json'
THRESH = 0.48
LOW = 0.30
ADAPT = 0.56          # confident live matches are learned (room/mic conditions)
MAX_LIVE = 40
last_secs = 0.0
_lock = threading.Lock()
_ex = sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(
    model=str(DIR / 'models' / 'spk.onnx'), num_threads=2))

def _pcm16k(wav_bytes):
    with wave.open(io.BytesIO(wav_bytes)) as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1: x = x.reshape(-1, ch).mean(axis=1)
    if sr != 16000:
        x = np.interp(np.arange(0, len(x), sr / 16000.0), np.arange(len(x)), x).astype(np.float32)
    # keep only the voiced part (simple energy gate) so silence doesn't dilute the voiceprint
    fr = 400; e = np.array([np.sqrt(np.mean(x[i:i + fr] ** 2)) for i in range(0, len(x) - fr, fr)] or [0])
    if e.max() > 0:
        keep = e > max(e.max() * 0.08, 1e-4)
        x = np.concatenate([x[i * fr:(i + 1) * fr] for i in np.nonzero(keep)[0]] or [x])
    return x.astype(np.float32)

def embed(wav_bytes):
    global last_secs
    x = _pcm16k(wav_bytes)
    last_secs = len(x) / 16000.0
    if len(x) < 16000 * 0.8: return None           # < 0.8 s of speech: too short to judge
    with _lock:
        s = _ex.create_stream(); s.accept_waveform(16000, x); s.input_finished()
        v = np.array(_ex.compute(s), dtype=np.float32)
    return v / (np.linalg.norm(v) or 1.0)

def _load():
    try: return json.loads(DB.read_text())
    except Exception: return {}

def enroll(name, wav_bytes):
    v = embed(wav_bytes)
    if v is None: return {'ok': False, 'error': 'too short'}
    db = _load(); db.setdefault(name, []).append(v.round(5).tolist())
    DB.write_text(json.dumps(db)); DB.chmod(0o600)
    return {'ok': True, 'name': name, 'count': len(db[name])}

def verify(wav_bytes):
    db = _load()
    if not db: return None, 0.0
    v = embed(wav_bytes)
    if v is None: return None, 0.0
    best, score = None, -1.0
    for n, embs in db.items():
        E = np.array(embs, dtype=np.float32)
        centroid = E.mean(axis=0); centroid /= np.linalg.norm(centroid) or 1.0
        s = max(float(centroid @ v), float(np.sort(E @ v)[-3:].mean()))   # centroid or best-3 average
        if s > score: best, score = n, s
    return (best if score >= THRESH else None), round(score, 3)

def adapt(name, wav_bytes, base=8):
    """Add a confidently-matched live clip; keep the first `base` enrolment clips + newest MAX_LIVE."""
    v = embed(wav_bytes)
    if v is None: return
    db = _load(); e = db.setdefault(name, [])
    e.append(v.round(5).tolist())
    if len(e) > base + MAX_LIVE: del e[base:len(e) - MAX_LIVE]
    DB.write_text(json.dumps(db))

def forget(name):
    db = _load(); n = db.pop(name, None); DB.write_text(json.dumps(db)); return n is not None
