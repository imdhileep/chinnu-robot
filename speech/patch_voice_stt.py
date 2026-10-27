p = 'voice.py'; s = open(p).read()
old = "def stt(wav_bytes, prompt=None):\n"
new = '''LOCAL_SPEECH = 'http://127.0.0.1:11436'      # Mac speech server via ssh tunnel (Telugu Whisper), when the Mac is on
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
'''
if 'LOCAL_SPEECH' not in s:
    assert s.count(old) == 1
    s = s.replace(old, new)
open(p, 'w').write(s); print('ok')
