"""voice-data/metadata.json -> HF audiofolder (train/ with metadata.csv) keeping only text the Telugu MMS tokenizer can read."""
import json, csv, os, shutil, soundfile as sf
SRC, DST = 'voice-data', 'voice-ds'
vocab = json.load(open('models/mms-tts-tel-train/vocab.json'))
meta = json.load(open(f'{SRC}/metadata.json'))
os.makedirs(f'{DST}/train', exist_ok=True)
kept, dropped, secs = 0, 0, 0.0
with open(f'{DST}/train/metadata.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['file_name', 'text'])
    for m in meta:
        t = ''.join(ch for ch in m['text'].replace('‌', '') if ch in vocab or ch == ' ')
        t = ' '.join(t.split())
        p = f"{SRC}/wavs/{m['file']}"
        try: d = sf.info(p).duration
        except Exception: dropped += 1; continue
        if len(t) < 4 or not (1.0 <= d <= 15.0): dropped += 1; continue
        shutil.copy(p, f"{DST}/train/{m['file']}"); w.writerow([m['file'], t]); kept += 1; secs += d
print('kept', kept, 'dropped', dropped, 'minutes', round(secs / 60, 1))
