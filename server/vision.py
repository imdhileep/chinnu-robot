"""Fast local object / person detection (YOLO11n ONNX via OpenCV DNN) + simple motion detection.
detect(jpg) -> [{'name','conf','box':[x,y,w,h],'cx','cy'}]  (cx, cy = centre as 0..1 of the frame)"""
import pathlib, threading
import numpy as np, cv2

MODEL = pathlib.Path(__file__).with_name('models') / 'yolo11n.onnx'
SIZE = 416
NAMES = ['person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat', 'traffic light',
         'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant',
         'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard',
         'sports ball', 'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket', 'bottle',
         'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange', 'broccoli',
         'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed', 'dining table', 'toilet',
         'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
         'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush']
_net = None
_lock = threading.Lock()

def _load():
    global _net
    if _net is None:
        _net = cv2.dnn.readNetFromONNX(str(MODEL))
    return _net

def _decode(jpg):
    return cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR) if isinstance(jpg, (bytes, bytearray)) else jpg

def detect(jpg, conf=0.35, only=None):
    img = _decode(jpg)
    if img is None: return []
    H, W = img.shape[:2]
    blob = cv2.dnn.blobFromImage(img, 1 / 255.0, (SIZE, SIZE), swapRB=True, crop=False)
    with _lock:
        net = _load(); net.setInput(blob); out = net.forward()
    p = out[0].T if out.shape[1] < out.shape[2] else out[0]          # (N, 4 + classes)
    scores = p[:, 4:]; cls = scores.argmax(1); sc = scores[np.arange(len(cls)), cls]
    keep = sc >= conf
    p, cls, sc = p[keep], cls[keep], sc[keep]
    boxes = []
    for (cx, cy, w, h) in p[:, :4]:
        boxes.append([float((cx - w / 2) * W / SIZE), float((cy - h / 2) * H / SIZE), float(w * W / SIZE), float(h * H / SIZE)])
    idx = cv2.dnn.NMSBoxes(boxes, sc.astype(float).tolist(), conf, 0.45) if boxes else []
    res = []
    for i in np.array(idx).flatten():
        name = NAMES[int(cls[i])] if int(cls[i]) < len(NAMES) else str(int(cls[i]))
        if only and name not in only: continue
        x, y, w, h = boxes[i]
        res.append({'name': name, 'conf': round(float(sc[i]), 2), 'box': [int(x), int(y), int(w), int(h)],
                    'cx': round((x + w / 2) / W, 3), 'cy': round((y + h / 2) / H, 3), 'area': round(w * h / (W * H), 3)})
    return sorted(res, key=lambda r: -r['area'])

def summary(objs):
    """'2 persons, 1 laptop, 1 cup' style text."""
    from collections import Counter
    c = Counter(o['name'] for o in objs)
    return ', '.join(f'{n} {k}{"s" if n > 1 else ""}' for k, n in c.most_common()) or 'nothing recognisable'

def motion(prev_jpg, cur_jpg, thresh=25, min_frac=0.01):
    """Returns {'moved': bool, 'frac': changed fraction, 'cx','cy'} of the biggest moving region."""
    a, b = _decode(prev_jpg), _decode(cur_jpg)
    if a is None or b is None or a.shape != b.shape: return {'moved': False, 'frac': 0}
    g1 = cv2.GaussianBlur(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), (21, 21), 0)
    g2 = cv2.GaussianBlur(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), (21, 21), 0)
    m = cv2.dilate(cv2.threshold(cv2.absdiff(g1, g2), thresh, 255, cv2.THRESH_BINARY)[1], None, iterations=2)
    frac = float(m.mean() / 255)
    out = {'moved': frac >= min_frac, 'frac': round(frac, 3)}
    if out['moved']:
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cs:
            x, y, w, h = cv2.boundingRect(max(cs, key=cv2.contourArea))
            out.update(cx=round((x + w / 2) / m.shape[1], 3), cy=round((y + h / 2) / m.shape[0], 3))
    return out
