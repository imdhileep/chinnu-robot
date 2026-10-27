"""Nightly: pull the photos Chinnu collected (finds + taught items), train a small fast YOLO11n on them,
and send the model to the Chinnu server so finding works even when this Mac is off.
Skips when there is too little new data. Log: /tmp/chinnu-vision-train.log"""
import os, json, random, shutil, subprocess, time
from pathlib import Path
HERE = Path(__file__).parent
DATA = HERE / 'data'
MIN_PER_CLASS, MIN_TOTAL = 15, 60

def sh(*a): return subprocess.run(a, capture_output=True, text=True)

def main():
    sh('rsync', '-az', 'chinnu-server:chinnu-agent/vision_data/', str(DATA) + '/')
    classes = json.load(open(DATA / 'classes.json')) if (DATA / 'classes.json').exists() else []
    labels = sorted((DATA / 'labels').glob('*.txt')) if (DATA / 'labels').exists() else []
    counts = {}
    for l in labels:
        for line in open(l):
            c = int(line.split()[0]); counts[c] = counts.get(c, 0) + 1
    keep = [i for i, n in counts.items() if n >= MIN_PER_CLASS]
    state = json.load(open(HERE / 'train_state.json')) if (HERE / 'train_state.json').exists() else {}
    if len(labels) < MIN_TOTAL or not keep or len(labels) == state.get('n'):
        print(time.strftime('%F %T'), f'skip: {len(labels)} photos, classes with enough data: {[classes[i] for i in keep]}'); return
    # build a YOLO dataset with only classes that have enough photos (re-indexed)
    ds = HERE / 'ds'; shutil.rmtree(ds, ignore_errors=True)
    remap = {old: new for new, old in enumerate(sorted(keep))}
    random.seed(1); random.shuffle(labels)
    for i, l in enumerate(labels):
        split = 'val' if i % 8 == 0 else 'train'
        lines = [ln.split() for ln in open(l)]
        lines = [[str(remap[int(p[0])])] + p[1:] for p in lines if int(p[0]) in remap]
        if not lines: continue
        (ds / split / 'images').mkdir(parents=True, exist_ok=True); (ds / split / 'labels').mkdir(parents=True, exist_ok=True)
        shutil.copy(DATA / 'images' / (l.stem + '.jpg'), ds / split / 'images')
        open(ds / split / 'labels' / l.name, 'w').write('\n'.join(' '.join(p) for p in lines) + '\n')
    names = [classes[o] for o in sorted(keep)]
    open(ds / 'data.yaml', 'w').write(f'path: {ds}\ntrain: train/images\nval: val/images\nnames: {json.dumps(names)}\n')
    from ultralytics import YOLO
    m = YOLO('yolo11n.pt')
    m.train(data=str(ds / 'data.yaml'), epochs=60, imgsz=640, batch=16, device='mps', project=str(HERE / 'runs'), name='custom', exist_ok=True, verbose=False)
    best = HERE / 'runs/custom/weights/best.pt'
    onnx = YOLO(str(best)).export(format='onnx', imgsz=640, opset=12)
    sh('scp', '-q', onnx, 'chinnu-server:chinnu-agent/models/custom_yolo.onnx')
    open('/tmp/custom_names.json', 'w').write(json.dumps(names))
    sh('scp', '-q', '/tmp/custom_names.json', 'chinnu-server:chinnu-agent/models/custom_yolo_names.json')
    json.dump({'n': len(labels), 'names': names, 'at': time.strftime('%F %T')}, open(HERE / 'train_state.json', 'w'))
    print(time.strftime('%F %T'), 'trained + deployed custom model for', names)

if __name__ == '__main__':
    main()
