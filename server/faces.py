"""Face enrol/identify for Chinnu using OpenCV YuNet (detect) + SFace (128-d embedding).
faces.json: {"Chintu": [[...128 floats...], ...]}.  Cosine similarity >= THRESH -> match (OpenCV docs: 0.363)."""
import os, json, threading, time
import numpy as np
import cv2

BASE = os.path.dirname(os.path.abspath(__file__))
DET = os.path.join(BASE, 'models', 'yunet.onnx')
REC = os.path.join(BASE, 'models', 'sface.onnx')
DB = os.path.join(BASE, 'faces.json')
THRESH = float(os.environ.get('CHINNU_FACE_THRESH', '0.40'))
_lock = threading.Lock()
_det = _rec = None

def _models():
    global _det, _rec
    if _det is None:
        _det = cv2.FaceDetectorYN.create(DET, '', (320, 320), 0.7, 0.3, 5000)
        _rec = cv2.FaceRecognizerSF.create(REC, '')
    return _det, _rec

def _load():
    try: return json.load(open(DB, encoding='utf-8'))
    except Exception: return {}

def _save(db):
    json.dump(db, open(DB, 'w', encoding='utf-8'))

def _decode(jpg):
    img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
    if img is None: raise ValueError('bad image')
    h, w = img.shape[:2]
    if max(h, w) > 1280:  # keep detection fast
        s = 1280 / max(h, w); img = cv2.resize(img, (int(w * s), int(h * s)))
    return img

def detect(img):
    det, _ = _models()
    h, w = img.shape[:2]
    det.setInputSize((w, h))
    _, faces = det.detect(img)
    return [] if faces is None else faces

def embed(img, face):
    _, rec = _models()
    aligned = rec.alignCrop(img, face)
    return rec.feature(aligned).flatten()

def _cos(a, b):
    a = np.asarray(a, dtype=np.float32); b = np.asarray(b, dtype=np.float32)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

def enroll(name, jpg):
    """Enrol the largest face in the image under `name`. Returns {'ok', 'name', 'count', 'faces'}"""
    name = (name or '').strip()
    if not name: return {'ok': False, 'error': 'name required'}
    with _lock:
        img = _decode(jpg)
        faces = detect(img)
        if len(faces) == 0: return {'ok': False, 'error': 'no face found'}
        face = max(faces, key=lambda f: f[2] * f[3])
        emb = embed(img, face)
        db = _load(); db.setdefault(name, []).append([round(float(x), 5) for x in emb])
        _save(db)
        return {'ok': True, 'name': name, 'count': len(db[name]), 'faces_in_image': len(faces)}

def identify(jpg, max_faces=5):
    """Returns {'ok', 'faces': [{'name'|None, 'score', 'box': [x,y,w,h], 'pos': 'left|center|right'}]}"""
    with _lock:
        img = _decode(jpg)
        W = img.shape[1]
        faces = sorted(detect(img), key=lambda f: -(f[2] * f[3]))[:max_faces]
        db = _load()
        out = []
        for f in faces:
            emb = embed(img, f)
            best, score = None, -1.0
            for n, embs in db.items():
                s = max((_cos(emb, e) for e in embs), default=-1.0)
                if s > score: best, score = n, s
            cx = f[0] + f[2] / 2
            pos = 'left' if cx < W / 3 else 'right' if cx > 2 * W / 3 else 'center'
            out.append({'name': best if score >= THRESH else None, 'score': round(score, 3),
                        'box': [int(f[0]), int(f[1]), int(f[2]), int(f[3])], 'pos': pos})
        return {'ok': True, 'faces': out, 'known': [x['name'] for x in out if x['name']]}

def people():
    return {n: len(v) for n, v in _load().items()}

def forget(name):
    with _lock:
        db = _load(); n = db.pop(name, None); _save(db)
        return {'ok': n is not None, 'name': name}

def describe(jpg):
    """One-line English hint for the vision prompt, or ''."""
    try:
        r = identify(jpg)
    except Exception as e:
        return ''
    if not r['faces']: return ''
    parts = []
    for f in r['faces']:
        parts.append(f"{f['name'] or 'unknown person'} ({f['pos']}, match {f['score']:.2f})")
    return 'Face recognition: ' + ', '.join(parts) + '.'

if __name__ == '__main__':
    import sys
    if sys.argv[1] == 'enroll': print(enroll(sys.argv[2], open(sys.argv[3], 'rb').read()))
    elif sys.argv[1] == 'id': print(identify(open(sys.argv[2], 'rb').read()))
    else: print(people())
