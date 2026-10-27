import re
p = 'dashboard.py'; s = open(p).read()

# 1) LAN copy: forward allowed /api/* calls to the main dashboard so every page sees the real state
old = """        if mac and mac in allow:
            return await call_next(request)"""
new = """        if mac and mac in allow:
            if request.url.path.startswith('/api/'):
                return await _lan_proxy(request)
            return await call_next(request)"""
assert s.count(old) == 1; s = s.replace(old, new)
proxy = '''
    async def _lan_proxy(request):
        from starlette.concurrency import run_in_threadpool
        body = await request.body()
        hdrs = {k: v for k, v in request.headers.items() if k.lower() in ('content-type', 'accept')}
        url = 'http://127.0.0.1:8080' + request.url.path + (('?' + request.url.query) if request.url.query else '')
        try:
            r = await run_in_threadpool(requests.request, request.method, url, data=body or None, headers=hdrs, timeout=150)
        except Exception as e:
            return JSONResponse({'ok': False, 'error': f'main server not answering: {e}'}, status_code=502)
        keep = {k: v for k, v in r.headers.items() if k.lower().startswith('x-') or k.lower() == 'cache-control'}
        return Response(r.content, status_code=r.status_code, media_type=r.headers.get('content-type'), headers=keep)
'''
anchor = "    @app.middleware('http')\n    async def _lan_guard"
assert s.count(anchor) == 1; s = s.replace(anchor, proxy + anchor)

# 2) app backend: feature status / uptime / alerts
if 'import uptime as _up' not in s:
    s += '''

import uptime as _up
app.include_router(_up.router)
if not os.environ.get('CHINNU_LAN'):
    _up.start(ROBOT, HDR)
'''
open(p, 'w').write(s); print('dashboard patched')
