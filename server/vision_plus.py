"""Chinnu's own vision features (server side). Heavy models run on the Mac vision server (open-vocabulary YOLO-World + CLIP),
reached at 127.0.0.1:11437 through the ssh tunnel; when the Mac is off, finding falls back to the on-server YOLO11n.
  find_object(name)     - turn the head around, look for it, point at it, send the photo, remember where it was
  teach_object(name)    - Chintu holds his own item in front of the camera; Chinnu learns THAT item (photos + CLIP gallery)
  teach_spot(name)      - "idi kitchen": Chinnu learns what this place looks like
  where_am_i()          - which taught spot Chinnu is in
  item_history(name)    - when/where an item was last seen
  watch loop            - every 15 min (idle, Mac on) checks the current view for watched items and updates last-seen
Data: vision_items.json, vision_spots.json, vision_seen.json, vision_data/ (photos + YOLO labels for training a custom model)."""
import os, io, json, time, threading, requests
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MAC = 'http://127.0.0.1:11437'
ITEMS, SPOTS, SEEN = (os.path.join(HERE, f) for f in ('vision_items.json', 'vision_spots.json', 'vision_seen.json'))
DATA = os.path.join(HERE, 'vision_data')
# things Chinnu watches for by default (lost-item finder + its own charger)
WATCH = ['keys', 'wallet', 'tv remote', 'eyeglasses', 'sunglasses', 'headphones', 'earbuds case', 'shoes', 'backpack',
         'water bottle', 'phone', 'phone charger', 'charging cable', 'power adapter', 'umbrella', 'watch', 'pen']
TE = {'taalaalu': 'keys', 'keys': 'keys', 'purse': 'wallet', 'wallet': 'wallet', 'remote': 'tv remote', 'kalla jodu': 'eyeglasses',
      'kallajodu': 'eyeglasses', 'specs': 'eyeglasses', 'glasses': 'eyeglasses', 'cheppulu': 'shoes', 'cheppu': 'shoes',
      'bag': 'backpack', 'bottle': 'water bottle', 'charger': 'phone charger', 'gadiyaram': 'watch'}
YAWS = [0, -40, 40, -75, 75]
_lock = threading.Lock()

def _j(p, d):
    try: return json.load(open(p))
    except Exception: return d
def _w(p, d): json.dump(d, open(p, 'w'), indent=1)

def mac_ok():
    try: return requests.get(f'{MAC}/health', timeout=1.5).ok
    except Exception: return False

def _robot():
    import robot; return robot.URL, robot.HDR

def snap():
    url, hdr = _robot()
    r = requests.get(f'{url}/snap.jpg', headers=hdr, timeout=8); r.raise_for_status(); return r.content

def head(yaw=0, pitch=0):
    url, hdr = _robot()
    try: requests.post(f'{url}/head', headers=hdr, params={'yaw': round(yaw), 'pitch': round(pitch), 'roll': 0, 'speed': 80}, timeout=5)
    except Exception: pass

def detect(jpg, classes, conf=0.15):
    r = requests.post(f'{MAC}/detect', params={'classes': ','.join(classes), 'conf': conf}, data=jpg, timeout=20)
    r.raise_for_status(); return r.json()

def embed(jpg, box=None):
    p = {'box': ','.join(str(int(v)) for v in box)} if box else {}
    r = requests.post(f'{MAC}/embed', params=p, data=jpg, timeout=20); r.raise_for_status()
    return np.array(r.json()['vec'], dtype='float32')

def _canon(name):
    """-> (item key, generic class to detect). Taught items first, then Telugu/English aliases."""
    n = name.lower().strip()
    items = _j(ITEMS, {})
    for k in items:
        if k == n or k in n or n in k: return k, items[k]['generic']
    for k, v in TE.items():
        if k in n: return v, v
    return n, n

COCO = {'tv remote': 'remote', 'phone': 'cell phone', 'water bottle': 'bottle', 'backpack': 'backpack', 'umbrella': 'umbrella',
        'cup': 'cup', 'laptop': 'laptop', 'book': 'book', 'scissors': 'scissors', 'handbag': 'handbag'}

_custom = {'net': None, 'names': None, 'mtime': 0}
def _custom_detect(jpg, item, conf=0.35):
    """Chinnu's own nightly-trained model (models/custom_yolo.onnx) for taught items / lost-item classes."""
    p = os.path.join(HERE, 'models/custom_yolo.onnx'); pn = os.path.join(HERE, 'models/custom_yolo_names.json')
    if not os.path.exists(p): return []
    import cv2
    if os.path.getmtime(p) != _custom['mtime']:
        _custom.update(net=cv2.dnn.readNetFromONNX(p), names=json.load(open(pn)), mtime=os.path.getmtime(p))
    names = _custom['names']
    if item not in names: return []
    img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR); H, W = img.shape[:2]
    net = _custom['net']; net.setInput(cv2.dnn.blobFromImage(img, 1 / 255.0, (640, 640), swapRB=True, crop=False))
    out = net.forward(); pr = out[0].T if out.shape[1] < out.shape[2] else out[0]
    sc = pr[:, 4:]; cls = sc.argmax(1); s = sc[np.arange(len(cls)), cls]
    res = []
    for i in np.where((s >= conf) & (cls == names.index(item)))[0]:
        cx, cy, w, h = pr[i, :4]
        res.append({'name': item, 'conf': float(s[i]), 'box': [(cx - w / 2) * W / 640, (cy - h / 2) * H / 640, (cx + w / 2) * W / 640, (cy + h / 2) * H / 640]})
    return sorted(res, key=lambda d: -d['conf'])[:3]

def _local_detect(jpg, generic, item=None):
    """Mac is off: Chinnu's own custom model first, then the on-server YOLO11n for COCO-type things."""
    try:
        r = _custom_detect(jpg, item or generic)
        if r: return r
    except Exception as e: print('[vision+] custom', e, flush=True)
    c = COCO.get(generic)
    if not c: return []
    try:
        import vision
        res = vision.detect(jpg, 0.25, [c]) or []
        out = []
        for d in (res if isinstance(res, list) else res.get('objects', [])):
            x, y, bw, bh = d['box']                       # vision.detect gives x, y, w, h
            out.append({'name': generic, 'conf': d.get('conf', 0.5), 'box': [x, y, x + bw, y + bh]})
        return out
    except Exception as e:
        print('[vision+] local', e, flush=True); return []

def _save_sample(jpg, cls, box, w, h):
    """Keep photo + YOLO-format label so a custom fast model can be trained later on the Mac."""
    os.makedirs(f'{DATA}/images', exist_ok=True); os.makedirs(f'{DATA}/labels', exist_ok=True)
    classes = _j(f'{DATA}/classes.json', [])
    if cls not in classes: classes.append(cls); _w(f'{DATA}/classes.json', classes)
    k = f"{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 1000:03d}"
    open(f'{DATA}/images/{k}.jpg', 'wb').write(jpg)
    x1, y1, x2, y2 = box
    open(f'{DATA}/labels/{k}.txt', 'w').write(f'{classes.index(cls)} {(x1 + x2) / 2 / w:.5f} {(y1 + y2) / 2 / h:.5f} {(x2 - x1) / w:.5f} {(y2 - y1) / h:.5f}\n')

def _annotate(jpg, box, label):
    import cv2
    im = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
    x1, y1, x2, y2 = [int(v) for v in box]
    cv2.rectangle(im, (x1, y1), (x2, y2), (0, 220, 255), 3)
    cv2.putText(im, label, (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 255), 2)
    os.makedirs(f'{DATA}/found', exist_ok=True)
    p = f"{DATA}/found/{time.strftime('%Y%m%d_%H%M%S')}.jpg"; cv2.imwrite(p, im)
    return p

def _telegram_photo(path, caption):
    try:
        import telegram_bot; telegram_bot.send_photo(open(path, 'rb').read(), caption)
    except Exception as e: print('[vision+] telegram', e, flush=True)

def _seen(item, yaw, photo, conf):
    s = _j(SEEN, {})
    spot = None
    try: spot = where_am_i(scan=False).get('spot')
    except Exception: pass
    s[item] = {'t': time.strftime('%Y-%m-%d %H:%M'), 'yaw': yaw, 'spot': spot, 'photo': photo, 'conf': conf}
    _w(SEEN, s)

def _match_own(jpg, box, item):
    """For Chintu's own taught items: is this box THAT item (CLIP similarity to the taught photos)?"""
    g = _j(ITEMS, {}).get(item, {}).get('vecs')
    if not g: return 1.0
    v = embed(jpg, box)
    return float(max(np.dot(np.array(g, dtype='float32'), v)))

def find_object(name, sweep=True):
    item, generic = _canon(name)
    use_mac = mac_ok()
    own = item in _j(ITEMS, {})
    best = None
    with _lock:
        for yaw in (YAWS if sweep else [None]):
            if yaw is not None:
                head(yaw, -10); time.sleep(0.9)
            try: jpg = snap()
            except Exception as e: return {'ok': False, 'error': f'camera: {e}'}
            if use_mac:
                r = detect(jpg, [generic]); objs, w, h = r['objects'], r['w'], r['h']
            else:
                objs, w, h = _local_detect(jpg, generic, item), 640, 360
            for o in objs:
                score = o['conf']
                if own and use_mac:
                    sim = _match_own(jpg, o['box'], item)
                    if sim < 0.72: continue
                    score = (score + sim) / 2
                if not best or score > best['score']:
                    best = {'score': score, 'yaw': yaw or 0, 'jpg': jpg, 'box': o['box'], 'w': w, 'h': h}
            if best and best['score'] > 0.55: break
        if not best:
            head(0, 0)
            last = _j(SEEN, {}).get(item)
            return {'ok': True, 'found': False, 'item': item, 'used': 'mac' if use_mac else 'pi',
                    'last_seen': last and {k: last[k] for k in ('t', 'spot') if last.get(k)},
                    'note': 'not visible from here' + ('' if use_mac else ' (Mac is off, only common objects can be found)')}
        # point the head at it
        cx = (best['box'][0] + best['box'][2]) / 2 / best['w']
        head(best['yaw'] - (cx - 0.5) * 60, -10)
    photo = _annotate(best['jpg'], best['box'], item)
    _seen(item, best['yaw'], photo, round(best['score'], 2))
    if use_mac and best['score'] > 0.4: _save_sample(best['jpg'], item, best['box'], best['w'], best['h'])
    side = 'right in front of me' if abs(best['yaw']) < 20 else 'to the side - my head is pointing at it'
    _telegram_photo(photo, f'🔎 Chinnu found your {item} ({side}, {time.strftime("%I:%M %p")})')
    return {'ok': True, 'found': True, 'item': item, 'where': side, 'confidence': round(best['score'], 2),
            'note': 'photo sent to Telegram; head is pointing at it'}

def teach_object(name, generic=None, seconds=8):
    """Chintu holds the item in front of Chinnu and turns it slowly; we keep ~10 views of THAT item."""
    if not mac_ok(): return {'ok': False, 'error': 'Mac is off - teaching needs the Mac vision server'}
    name = name.lower().strip(); generic = (generic or TE.get(name, name)).lower()
    vecs, kept = [], 0
    with _lock:
        head(0, -5); time.sleep(0.6)
        t_end = time.time() + seconds
        while time.time() < t_end and kept < 12:
            jpg = snap()
            r = detect(jpg, [generic, 'object held in hand'], conf=0.1)
            if r['objects']:
                o = r['objects'][0]
                vecs.append(embed(jpg, o['box']).tolist()); kept += 1
                _save_sample(jpg, name, o['box'], r['w'], r['h'])
            time.sleep(0.4)
    if kept < 3: return {'ok': False, 'error': f'could not see the {name} clearly - hold it closer, in good light', 'views': kept}
    items = _j(ITEMS, {}); items[name] = {'generic': generic, 'vecs': vecs, 'taught': time.strftime('%Y-%m-%d %H:%M')}
    _w(ITEMS, items)
    return {'ok': True, 'learned': name, 'views': kept, 'detects_as': generic}

def teach_spot(name):
    if not mac_ok(): return {'ok': False, 'error': 'Mac is off - teaching needs the Mac vision server'}
    name = name.lower().strip(); vecs = []
    with _lock:
        for yaw in (0, -40, 40):
            head(yaw, 0); time.sleep(0.8); vecs.append(embed(snap()).tolist())
        head(0, 0)
    spots = _j(SPOTS, {}); spots.setdefault(name, []).extend(vecs); spots[name] = spots[name][-15:]
    _w(SPOTS, spots)
    return {'ok': True, 'learned_spot': name, 'views': len(spots[name]), 'all_spots': sorted(spots)}

def where_am_i(scan=True):
    spots = _j(SPOTS, {})
    if not spots: return {'ok': True, 'spot': None, 'note': 'no spots taught yet - say "Chinnu, idi <place>" to teach one'}
    if not mac_ok(): return {'ok': False, 'error': 'Mac is off'}
    v = embed(snap())
    scores = {k: float(max(np.dot(np.array(vs, dtype='float32'), v))) for k, vs in spots.items()}
    best = max(scores, key=scores.get)
    return {'ok': True, 'spot': best if scores[best] > 0.8 else None, 'scores': {k: round(s, 2) for k, s in scores.items()}}

def item_history(name):
    item, _ = _canon(name)
    s = _j(SEEN, {}).get(item)
    return {'item': item, 'last_seen': s} if s else {'item': item, 'last_seen': None, 'note': 'never seen yet'}

def status():
    return {'mac': mac_ok(), 'taught_items': sorted(_j(ITEMS, {})), 'spots': sorted(_j(SPOTS, {})),
            'seen': _j(SEEN, {}), 'samples': len(os.listdir(f'{DATA}/images')) if os.path.isdir(f'{DATA}/images') else 0}

def _watch_loop():
    """Every 15 min: if idle and the Mac is on, glance at the current view and update last-seen for watched/taught items."""
    time.sleep(120)
    while True:
        try:
            idle = True
            try:
                import behaviors; s = behaviors.status(); idle = not (s.get('guard') or s.get('follow'))
            except Exception: pass
            if idle and mac_ok() and not _lock.locked():
                jpg = snap(); items = _j(ITEMS, {})
                classes = sorted(set(WATCH) | {v['generic'] for v in items.values()})
                r = detect(jpg, classes, conf=0.35)
                for o in r['objects']:
                    name = o['name']
                    for k, v in items.items():
                        if v['generic'] == name and _match_own(jpg, o['box'], k) > 0.75: name = k
                    _seen(name, 0, None, o['conf'])
        except Exception as e:
            print('[vision+] watch', e, flush=True)
        time.sleep(900)

def start():
    threading.Thread(target=_watch_loop, daemon=True).start()
