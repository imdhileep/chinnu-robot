import shutil, time
fn = 'mobile.py'
s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_watch' + time.strftime('%H%M%S'))
s += '''

@router.post('/api/watch')
async def api_watch(request: Request):
    """Apple Watch / Siri Shortcut: {"text": "...", "speak": false} -> plain-text reply.
    The watch is on Chintu's wrist and the URL is tailnet-only, so it runs in owner mode."""
    from fastapi.responses import PlainTextResponse
    import requests as _rq, owner
    try: d = await request.json()
    except Exception: d = {}
    text = str(d.get('text') or '').strip()
    if not text: return PlainTextResponse('Emi cheppaledu anna')
    owner.unlock(15, 'watch')
    try:
        r = _rq.post('http://127.0.0.1:8081/chat', json={'text': text, 'speak': bool(d.get('speak', False))}, timeout=90).json()
        return PlainTextResponse(r.get('reply') or 'Ok anna')
    except Exception as e:
        return PlainTextResponse('Chinnu busy ga vundi, malli try cheyi')
'''
open(fn, 'w', encoding='utf-8').write(s); print('patched')
