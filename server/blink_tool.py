"""Blink cameras for Chinnu (blinkpy). One-time login: `venv/bin/python blink_login.py` (saves blink_auth.json).
snapshot(name) -> jpeg bytes (fresh picture), cameras() -> [{name, armed, battery, last_motion, ...}]."""
import os, asyncio, time, json, threading
BASE = os.path.dirname(os.path.abspath(__file__))
AUTH_FILE = os.path.join(BASE, 'blink_auth.json')
_lock = threading.Lock()
_cache = {'at': 0, 'cams': None}

def _alias(name):
    return ''.join(ch for ch in name.lower() if ch.isalnum())

async def _open(session):
    from blinkpy.blinkpy import Blink
    from blinkpy.auth import Auth
    from blinkpy.helpers.util import json_load
    if not os.path.exists(AUTH_FILE):
        raise RuntimeError('blink not logged in: run venv/bin/python blink_login.py')
    blink = Blink(session=session, refresh_rate=5)
    blink.auth = Auth(await json_load(AUTH_FILE), no_prompt=True, session=session)
    ok = await blink.start()
    if not ok:
        raise RuntimeError('blink login failed (token expired?) - rerun blink_login.py')
    await blink.save(AUTH_FILE)
    return blink

def _find(blink, name):
    want = _alias(name or '')
    for n, cam in blink.cameras.items():
        if not want or _alias(n) == want or want in _alias(n) or _alias(n) in want:
            return n, cam
    raise RuntimeError(f"camera '{name}' not found; have: {list(blink.cameras)}")

async def _cameras():
    from aiohttp import ClientSession
    async with ClientSession() as s:
        blink = await _open(s)
        out = []
        for n, cam in blink.cameras.items():
            a = cam.attributes or {}
            out.append({'name': n, 'armed': a.get('motion_enabled'), 'battery': a.get('battery'), 'battery_voltage': a.get('battery_voltage'),
                        'temperature': a.get('temperature'), 'last_record': a.get('last_record'), 'motion_detected': a.get('motion_detected'),
                        'thumbnail': bool(a.get('thumbnail'))})
        return out

async def _snapshot(name, wait=6):
    from aiohttp import ClientSession
    async with ClientSession() as s:
        blink = await _open(s)
        n, cam = _find(blink, name)
        try:
            await cam.snap_picture()
            await asyncio.sleep(wait)
            await blink.refresh(force=True)
        except Exception as e:
            print('[blink] snap failed, using last thumbnail:', e, flush=True)
        img = cam.image_from_cache
        if not img:
            await blink.refresh(force=True)
            img = cam.image_from_cache
        if not img:
            raise RuntimeError('no image from camera')
        return n, img

def _run(coro):
    with _lock:
        return asyncio.run(coro)

def cameras(max_age=120):
    if _cache['cams'] and time.time() - _cache['at'] < max_age:
        return _cache['cams']
    cams = _run(_cameras()); _cache.update(at=time.time(), cams=cams)
    return cams

def names():
    try: return [c['name'] for c in cameras()]
    except Exception: return []

def snapshot(name=None):
    """Returns (camera_name, jpeg_bytes)."""
    return _run(_snapshot(name))

if __name__ == '__main__':
    import sys
    print(json.dumps(cameras(), indent=1, default=str))
    if len(sys.argv) > 1:
        n, img = snapshot(sys.argv[1]); open('/tmp/blink.jpg', 'wb').write(img); print(n, len(img), 'bytes -> /tmp/blink.jpg')
