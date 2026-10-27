"""Chinnu vision server on the Mac (127.0.0.1:8092; the Chinnu server reaches it as 127.0.0.1:11437 via the ssh tunnel).
/detect : JPEG + ?classes=keys,wallet,tv remote  -> boxes (open-vocabulary YOLO-World: any object name, no training needed)
/embed  : JPEG (+ optional box) -> CLIP embedding, used to recognise Chintu's OWN items and home spots by example
/health"""
import io, time, threading, numpy as np
from PIL import Image
from fastapi import FastAPI, Request
from ultralytics import YOLOWorld
import torch, clip

DEV = 'mps' if torch.backends.mps.is_available() else 'cpu'
app = FastAPI(title='Chinnu vision')
_lock = threading.Lock()
world = YOLOWorld('yolov8l-worldv2.pt')
_cur = {'classes': None}
cmodel, cprep = clip.load('ViT-B/32', device=DEV)
stats = {'detect': 0, 'embed': 0}

def _img(b): return Image.open(io.BytesIO(b)).convert('RGB')

@app.post('/detect')
async def detect(req: Request, classes: str, conf: float = 0.12):
    im = _img(await req.body())
    names = [c.strip() for c in classes.split(',') if c.strip()][:40]
    t = time.time()
    with _lock:
        if names != _cur['classes']:
            world.set_classes(names); _cur['classes'] = names
        r = world.predict(im, conf=conf, verbose=False, device=DEV)[0]
    out = []
    for b in r.boxes:
        x1, y1, x2, y2 = [round(float(v)) for v in b.xyxy[0]]
        out.append({'name': names[int(b.cls)], 'conf': round(float(b.conf), 3), 'box': [x1, y1, x2, y2]})
    out.sort(key=lambda d: -d['conf'])
    stats['detect'] += 1
    return {'objects': out, 'w': im.width, 'h': im.height, 'secs': round(time.time() - t, 2)}

@app.post('/embed')
async def embed(req: Request, box: str = ''):
    im = _img(await req.body())
    if box:
        x1, y1, x2, y2 = [int(v) for v in box.split(',')]
        pad = int(0.08 * max(x2 - x1, y2 - y1))
        im = im.crop((max(0, x1 - pad), max(0, y1 - pad), min(im.width, x2 + pad), min(im.height, y2 + pad)))
    with _lock, torch.no_grad():
        v = cmodel.encode_image(cprep(im).unsqueeze(0).to(DEV)).float()
        v = (v / v.norm(dim=-1, keepdim=True))[0].cpu().numpy()
    stats['embed'] += 1
    return {'vec': [round(float(x), 5) for x in v]}

@app.get('/health')
def health(): return {'ok': True, 'device': DEV, **stats}
