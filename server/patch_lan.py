import shutil, time
fn = 'dashboard.py'
s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_lan' + time.strftime('%H%M%S'))
for a in ("threading.Thread(target=_robot_poll, daemon=True).start()",
          "threading.Thread(target=_nc_startup_sync, daemon=True).start()"):
    assert s.count(a) == 1, a
    s = s.replace(a, "if not os.environ.get('CHINNU_LAN'): " + a)
a = "app = FastAPI(title='Chinnu Dashboard')\n"
assert s.count(a) == 1
s = s.replace(a, a + '''
# ---- LAN listener guard (Quest 3 on home Wi-Fi): only allow-listed devices by MAC ----
if os.environ.get('CHINNU_LAN'):
    import json as _j, pathlib as _pl
    _ALLOW = _pl.Path(__file__).with_name('lan_allow.json')
    _PEND = _pl.Path(__file__).with_name('lan_pending.json')
    def _mac(ip):
        try:
            for line in open('/proc/net/arp').read().splitlines()[1:]:
                p = line.split()
                if p[0] == ip: return p[3].lower()
        except Exception: pass
        return ''
    @app.middleware('http')
    async def _lan_guard(request, call_next):
        ip = request.client.host if request.client else ''
        mac = _mac(ip)
        try: allow = _j.loads(_ALLOW.read_text())
        except Exception: allow = {}
        if mac and mac in allow:
            return await call_next(request)
        try:
            pend = _j.loads(_PEND.read_text()) if _PEND.exists() else {}
            pend[mac or ip] = {'ip': ip, 'ua': request.headers.get('user-agent', '')[:200], 'at': time.strftime('%Y-%m-%d %H:%M:%S')}
            _PEND.write_text(_j.dumps(pend, indent=1))
        except Exception: pass
        return HTMLResponse('<h2 style="font-family:sans-serif">Chinnu: ee device ki permission ledu.</h2>', status_code=403)
''')
open(fn, 'w', encoding='utf-8').write(s); print('patched')
