import os, io, subprocess, requests, yaml
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
CFG = yaml.safe_load(open('config.yaml', encoding='utf-8-sig'))
URL = CFG['robot']['url']
HDR = {'x-token': os.environ.get('CHINNU_TOKEN', '')}
V = CFG.get('voice', {})
client = OpenAI()

CHILD_INSTRUCTIONS = (
    'Speak like an adorable, cheerful little 4-year-old child - a bright, '
    'high-pitched, playful, giggly small voice, full of excitement and wonder. '
    'Clear, natural Telugu; warm and sweet; no animal noises or sound effects.')

try:
    import httpx2 as httpx
except ImportError:
    import httpx
# TTS: fail fast on stalled connections (OpenAI sometimes hangs a stream for 60-90 s) and retry once
try:
    import usage; usage.install()
except Exception as _e: print("[usage]", _e)
_tts_client = client.with_options(timeout=httpx.Timeout(20.0, connect=5.0, read=8.0, write=10.0), max_retries=1)


OWN_VOICE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'own_voice.json')
tts_stats = {'own': 0, 'openai': 0, 'last': None}

def own_voice_on():
    try:
        import json as _json; return bool(_json.load(open(OWN_VOICE_FILE)).get('on'))
    except Exception: return False

def set_own_voice(on):
    import json as _json; _json.dump({'on': bool(on)}, open(OWN_VOICE_FILE, 'w')); return own_voice_on()

def _tts_own(text):
    """WAV bytes in Chinnu's own voice from the Mac, or None."""
    if not own_voice_on(): return None
    try:
        r = requests.post(f'{LOCAL_SPEECH}/tts', json={'text': text}, timeout=20)
        if r.ok and len(r.content) > 1000:
            tts_stats['own'] += 1; tts_stats['last'] = 'own'; return r.content
    except Exception: pass
    return None

def tts(text, path='/tmp/chinnu_tts.wav'):
    own = _tts_own(text)
    if own:
        open(path, 'wb').write(own); return path
    tts_stats['openai'] += 1; tts_stats['last'] = 'openai'
    raw = '/tmp/chinnu_tts_raw.wav'
    resp = _tts_client.audio.speech.create(model=V.get('tts_model', 'gpt-4o-mini-tts'), voice=V.get('voice', 'echo'),
                                      input=text, response_format='wav', instructions=CHILD_INSTRUCTIONS)
    resp.write_to_file(raw)
    pitch = ['pitch', str(V.get('child_pitch', 600))] if V.get('child_voice', True) else []
    try:
        subprocess.run(['sox', raw, path, 'norm', '-1', *pitch, 'compand', '0.1,0.2', '-60,-40,-20,-5,0,-3', '0', '-90', '0.1'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        path = raw
    return path

def say_stream(text):
    if own_voice_on():
        return say(text)            # own voice: whole sentence WAV via /say
    """Stream TTS PCM (24 kHz s16 mono) straight to the robot's /say/stream so playback starts after ~0.4 s.
    Pitch shift (child voice) is done on the robot with sox in streaming mode. Falls back to say() on error."""
    pitch = int(V.get('child_pitch', 600)) if V.get('child_voice', True) else 0
    def gen():
        with _tts_client.audio.speech.with_streaming_response.create(
                model=V.get('tts_model', 'gpt-4o-mini-tts'), voice=V.get('voice', 'echo'), input=text,
                response_format='pcm', instructions=CHILD_INSTRUCTIONS) as resp:
            for chunk in resp.iter_bytes(chunk_size=4096):
                if chunk: yield chunk
    try:
        r = requests.post(f'{URL}/say/stream', headers={**HDR, 'Content-Type': 'application/octet-stream'},
                          params={'rate': 24000, 'pitch': pitch}, data=gen(), timeout=90)
        if r.ok: return r.json()
        print('[say_stream] robot said', r.status_code, r.text[:80], '- falling back')
    except Exception as e:
        print('[say_stream] error', e, '- falling back')
    return say(text)

_credit_warned = [0.0]
def credit_alert(err):
    """OpenAI out of credits -> tell Chintu on Telegram (at most once an hour)."""
    import time as _t
    m = str(err)
    if not any(k in m for k in ('insufficient_quota', 'credits', 'credit_balance')): return
    if _t.time() - _credit_warned[0] < 3600: return
    _credit_warned[0] = _t.time()
    try:
        import telegram_bot
        telegram_bot.send('⚠️ Chinnu: OpenAI credits are finished, so I cannot hear or talk. Add credits at platform.openai.com/settings/organization/billing')
    except Exception as e: print('[credit alert]', e, flush=True)

def say(text):
    try: path = tts(text)
    except Exception as e:
        print('[tts] failed:', str(e)[:120], flush=True); credit_alert(e); return {'ok': False, 'error': str(e)[:200]}
    r = requests.post(f'{URL}/say', headers=HDR, data=open(path, 'rb').read(), timeout=60)
    return r.json() if r.ok else {'ok': False, 'error': r.text}

def listen(seconds=5):
    r = requests.post(f'{URL}/listen', headers=HDR, params={'seconds': seconds}, timeout=seconds + 15)
    if not r.ok:
        return None, 0.0
    if r.headers.get('X-Spoke') == '0':   # VAD on the robot saw no speech at all
        return None, float(r.headers.get('X-RMS', '0'))
    return r.content, float(r.headers.get('X-RMS', '0'))

LOCAL_SPEECH = 'http://127.0.0.1:11436'      # Mac speech server via ssh tunnel (Telugu Whisper), when the Mac is on
stt_stats = {'mac': 0, 'openai': 0, 'last': None}

def stt(wav_bytes, prompt=None):
    if V.get('local_stt', True):
        try:
            r = requests.post(f'{LOCAL_SPEECH}/stt', data=wav_bytes, timeout=8)
            if r.ok:
                stt_stats['mac'] += 1; stt_stats['last'] = 'mac'
                return (r.json().get('text') or '').strip()
        except Exception:
            pass
    stt_stats['openai'] += 1; stt_stats['last'] = 'openai'
    return _stt_openai(wav_bytes, prompt)

def _stt_openai(wav_bytes, prompt=None):
    f = io.BytesIO(wav_bytes); f.name = 'q.wav'
    kw = dict(model=V.get('stt_model', 'gpt-4o-transcribe'), file=f, language=V.get('stt_language', 'te'))
    if prompt: kw['prompt'] = prompt
    try:
        return (client.audio.transcriptions.create(**kw).text or '').strip()
    except Exception as e:
        print('[STT error]', e); return ''

if __name__ == '__main__':
    import sys
    print(say(sys.argv[1] if len(sys.argv) > 1 else 'Hai anna! Nenu Chinnu, ippudu server nunchi matladutunna!'))
