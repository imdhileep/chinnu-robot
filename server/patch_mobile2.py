m = open('mobile.py', encoding='utf-8').read()
if '/api/home' in m: print('already'); raise SystemExit

# ---------- backend: device state + phone push-to-talk ----------
api = '''
_home_cache = {'t': 0, 'data': None}

@router.get('/api/home')
def home_state(fresh: int = 0):
    """Power strip + Govee plug state (cached 15 s; Govee is a cloud API)."""
    import time as _t
    if not fresh and _home_cache['data'] and _t.time() - _home_cache['t'] < 15:
        return _home_cache['data']
    out = {'strip': None, 'govee': None}
    try:
        import tuya_strip; out['strip'] = tuya_strip.status()
    except Exception as e: out['strip_error'] = str(e)[:120]
    try:
        import govee_plug; out['govee'] = govee_plug.status(); out['locked'] = sorted(govee_plug.LOCKED)
    except Exception as e: out['govee_error'] = str(e)[:120]
    _home_cache.update(t=_t.time(), data=out)
    return out

@router.post('/api/plug/{kind}/{target}/{act}')
def plug_set(kind: str, target: str, act: str):
    _home_cache['t'] = 0
    if kind == 'strip':
        import tuya_strip; return tuya_strip.set_outlet(target, act == 'on')
    import govee_plug; return govee_plug.set_plug(target, act == 'on')

@router.post('/api/voice')
async def phone_voice(request: Request):
    """Phone push-to-talk: audio blob -> transcript -> Chinnu answers out loud (and in the chat)."""
    import io, requests as _rq, voice
    body = await request.body()
    ct = request.headers.get('content-type', 'audio/webm')
    ext = 'mp4' if 'mp4' in ct or 'm4a' in ct or 'aac' in ct else ('ogg' if 'ogg' in ct else 'webm')
    if len(body) < 2000: return {'ok': False, 'error': 'too short'}
    f = io.BytesIO(body); f.name = f'phone.{ext}'
    text = voice.client.audio.transcriptions.create(model='gpt-4o-transcribe', file=f, language='te').text.strip()
    if text:
        import threading
        threading.Thread(target=lambda: _rq.post('http://127.0.0.1:8081/chat', json={'text': text, 'speak': True}, timeout=120), daemon=True).start()
    return {'ok': True, 'text': text}

@router.get('/m', response_class=HTMLResponse)'''
m = m.replace("\n@router.get('/m', response_class=HTMLResponse)", api, 1)
m = m.replace('from fastapi import APIRouter\n', 'from fastapi import APIRouter, Request\n', 1)
open('mobile.py', 'w', encoding='utf-8').write(m); print('backend ok')
