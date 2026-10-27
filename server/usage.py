"""Chinnu's own OpenAI usage meter (all processes write to logs/usage-YYYY-MM-DD.jsonl).
install() patches the OpenAI SDK so every chat / speech / transcription call is counted automatically;
realtime turns are recorded from realtime.py. Costs are ESTIMATES from the price table in config.yaml (usage_prices)."""
import os, json, time, threading, glob, wave, io

BASE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE, 'logs')
_lock = threading.Lock()
_installed = [False]

# USD per 1M tokens unless noted. Override in config.yaml -> usage_prices.
PRICES = {
    'gpt-4.1': {'in': 2.00, 'out': 8.00},
    'gpt-4o-mini': {'in': 0.15, 'out': 0.60},
    'gpt-4o': {'in': 2.50, 'out': 10.00},
    'gpt-realtime': {'text_in': 4.00, 'text_out': 16.00, 'audio_in': 32.00, 'audio_out': 64.00, 'cached_in': 0.40},
    'gpt-4o-transcribe': {'per_min': 0.006},
    'gpt-4o-mini-transcribe': {'per_min': 0.003},
    'gpt-4o-mini-tts': {'per_1k_chars': 0.015},
}

def _prices():
    try:
        import yaml
        p = (yaml.safe_load(open(os.path.join(BASE, 'config.yaml'), encoding='utf-8-sig')) or {}).get('usage_prices') or {}
        out = {k: dict(v) for k, v in PRICES.items()}
        for k, v in p.items(): out.setdefault(k, {}).update(v)
        return out
    except Exception:
        return PRICES

def cost(rec, P=None):
    P = P or _prices(); m = rec.get('model', ''); p = P.get(m) or next((v for k, v in P.items() if m.startswith(k)), {})
    k = rec.get('kind')
    if k == 'chat':
        return (rec.get('in', 0) * p.get('in', 0) + rec.get('out', 0) * p.get('out', 0)) / 1e6
    if k == 'realtime':
        return (rec.get('text_in', 0) * p.get('text_in', 0) + rec.get('text_out', 0) * p.get('text_out', 0) +
                rec.get('audio_in', 0) * p.get('audio_in', 0) + rec.get('audio_out', 0) * p.get('audio_out', 0) +
                rec.get('cached_in', 0) * p.get('cached_in', 0)) / 1e6
    if k == 'stt':
        return rec.get('seconds', 0) / 60 * p.get('per_min', 0.006)
    if k == 'tts':
        return rec.get('chars', 0) / 1000 * p.get('per_1k_chars', 0.015)
    return 0.0

def record(kind, model, **nums):
    rec = {'t': time.strftime('%H:%M:%S'), 'kind': kind, 'model': model, 'src': os.path.basename(os.sys.argv[0] or '?'), **nums}
    try:
        rec['usd'] = round(cost(rec), 6)
        with _lock, open(os.path.join(LOG_DIR, time.strftime('usage-%Y-%m-%d.jsonl')), 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec) + '\n')
    except Exception as e:
        print('[usage]', e, flush=True)

def _audio_seconds(f):
    try:
        data = f.getvalue() if hasattr(f, 'getvalue') else (f.read() if hasattr(f, 'read') else None)
        if hasattr(f, 'seek'): f.seek(0)
        if not data: return 0.0
        try:
            with wave.open(io.BytesIO(data)) as w: return w.getnframes() / float(w.getframerate())
        except Exception:
            return len(data) / 16000.0          # compressed (webm/m4a): ~16 kB/s rough guess
    except Exception:
        return 0.0

class _StreamProxy:
    """Wraps a streaming chat response: passes chunks through untouched, counts output chars."""
    def __init__(self, s, model, in_tok):
        self._s, self._m, self._in, self._chars = s, model, in_tok, 0
    def __iter__(self):
        try:
            for c in self._s:
                try:
                    if c.choices and c.choices[0].delta and c.choices[0].delta.content: self._chars += len(c.choices[0].delta.content)
                except Exception: pass
                yield c
        finally:
            record('chat', self._m, **{'in': self._in, 'out': self._chars // 3 + 1, 'estimated': True})
    def __getattr__(self, k): return getattr(self._s, k)
    def __enter__(self): return self
    def __exit__(self, *a):
        try: self._s.close()
        except Exception: pass

def install():
    if _installed[0]: return
    _installed[0] = True
    try:
        from openai.resources.chat.completions import Completions
        from openai.resources.audio.transcriptions import Transcriptions
        from openai.resources.audio.speech import Speech
    except Exception as e:
        print('[usage] patch failed', e, flush=True); return
    orig_chat, orig_stt, orig_tts = Completions.create, Transcriptions.create, Speech.create

    def chat(self, *a, **kw):
        r = orig_chat(self, *a, **kw); m = kw.get('model', '?')
        try:
            if kw.get('stream'):
                in_tok = sum(len(str(x.get('content', ''))) for x in kw.get('messages', []) if isinstance(x, dict)) // 3
                return _StreamProxy(r, m, in_tok)
            u = getattr(r, 'usage', None)
            if u: record('chat', m, **{'in': u.prompt_tokens, 'out': u.completion_tokens})
        except Exception: pass
        return r

    def stt(self, *a, **kw):
        secs = _audio_seconds(kw.get('file'))
        r = orig_stt(self, *a, **kw)
        record('stt', kw.get('model', '?'), seconds=round(secs, 1))
        return r

    def tts(self, *a, **kw):
        r = orig_tts(self, *a, **kw)
        record('tts', kw.get('model', '?'), chars=len(kw.get('input', '')))
        return r

    Completions.create, Transcriptions.create, Speech.create = chat, stt, tts

def summary(day=None):
    day = day or time.strftime('%Y-%m-%d')
    p = os.path.join(LOG_DIR, f'usage-{day}.jsonl')
    tot = {'usd': 0.0, 'by_kind': {}, 'by_model': {}, 'calls': 0, 'stt_min': 0.0, 'tts_chars': 0, 'realtime_turns': 0}
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            try: r = json.loads(line)
            except Exception: continue
            u = r.get('usd', 0); tot['usd'] += u; tot['calls'] += 1
            tot['by_kind'][r['kind']] = round(tot['by_kind'].get(r['kind'], 0) + u, 4)
            tot['by_model'][r['model']] = round(tot['by_model'].get(r['model'], 0) + u, 4)
            if r['kind'] == 'stt': tot['stt_min'] += r.get('seconds', 0) / 60
            if r['kind'] == 'tts': tot['tts_chars'] += r.get('chars', 0)
            if r['kind'] == 'realtime': tot['realtime_turns'] += 1
    tot['usd'] = round(tot['usd'], 4); tot['stt_min'] = round(tot['stt_min'], 1)
    return tot

def history(days=14):
    out = []
    for p in sorted(glob.glob(os.path.join(LOG_DIR, 'usage-*.jsonl')))[-days:]:
        d = os.path.basename(p)[6:16]; s = summary(d)
        out.append({'day': d, 'usd': s['usd'], 'calls': s['calls']})
    return out
