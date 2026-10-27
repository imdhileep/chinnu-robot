"""Chinnu music player: plays a song on the PiDog speaker.
Looks in the home music folders first (your own songs, e.g. Suno songs dropped into Nextcloud Chinnu/music),
otherwise finds the song on YouTube (yt-dlp) and streams the audio through ffmpeg -> robot /say/stream."""
import os, re, time, threading, subprocess, pathlib, requests
import voice

YTDLP = str(pathlib.Path(__file__).with_name('venv') / 'bin' / 'yt-dlp')
LOCAL_DIRS = ['/mnt/hdd/media/Music', '/mnt/hdd/nextcloud/data/dk/files/Chinnu/music', '/mnt/hdd/old-laptop']
EXTS = ('.mp3', '.m4a', '.flac', '.wav', '.ogg', '.opus', '.aac')
_cur = {'title': None, 'source': None, 'stop': None, 'ffmpeg': None, 'started': None, 'queue': [], 'src': None, 'offset': 0.0}
_paused = {}
_lock = threading.Lock()

def _norm(s): return re.sub(r'[^a-z0-9ఀ-౿]+', ' ', s.lower()).strip()

def find_local(query):
    q = set(_norm(query).split()) - {'song', 'songs', 'paata', 'play', 'the', 'a'}
    if not q: return None
    best, score = None, 0
    for d in LOCAL_DIRS:
        if not os.path.isdir(d): continue
        for root, _, files in os.walk(d):
            for f in files:
                if not f.lower().endswith(EXTS): continue
                words = set(_norm(f).split())
                s = len(q & words) / len(q)
                if s > score: best, score = os.path.join(root, f), s
    return best if score >= 0.6 else None

def find_youtube(query):
    r = subprocess.run([YTDLP, '-f', 'bestaudio', '--no-playlist', '--print', 'title', '--print', 'url',
                        f'ytsearch1:{query} song audio'], capture_output=True, text=True, timeout=60)
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    if len(lines) >= 2: return lines[0], lines[1]
    return None, None

def _player(src, title, stop_evt, delay, offset=0.0):
    if delay: time.sleep(delay)                 # let Chinnu finish saying "playing ..." first
    if stop_evt.is_set(): return
    seek = ['-ss', str(int(offset))] if offset > 1 else []
    _cur['started'] = time.time(); _cur['offset'] = offset
    ff = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-reconnect', '1', '-reconnect_streamed', '1', *seek, '-i', src,
                           '-f', 's16le', '-ac', '1', '-ar', '24000', '-af', 'volume=0.8', '-'],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) if src.startswith('http') else \
         subprocess.Popen(['ffmpeg', '-loglevel', 'error', *seek, '-i', src, '-f', 's16le', '-ac', '1', '-ar', '24000', '-af', 'volume=0.8', '-'],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    _cur['ffmpeg'] = ff
    def gen():
        while not stop_evt.is_set():
            b = ff.stdout.read(9600)            # 0.2 s of audio
            if not b: return
            yield b
    try:
        requests.post(f'{voice.URL}/say/stream', headers={**voice.HDR, 'Content-Type': 'application/octet-stream'},
                      params={'rate': 24000, 'pitch': 0}, data=gen(), timeout=1800)
    except Exception as e:
        print('[music] stream error', e, flush=True)
    finally:
        try: ff.kill()
        except Exception: pass
        with _lock:
            if _cur['stop'] is stop_evt:
                _cur.update(title=None, source=None, stop=None, ffmpeg=None)
    print(f'[music] finished: {title}', flush=True)

def play(query, delay=4.0):
    stop()
    _paused.clear()
    path = find_local(query)
    if path:
        src, title, source = path, os.path.splitext(os.path.basename(path))[0], 'home library'
    else:
        title, src = find_youtube(query)
        if not src: return {'ok': False, 'error': f'could not find "{query}"'}
        source = 'YouTube'
    ev = threading.Event()
    with _lock:
        _cur.update(title=title, source=source, stop=ev, started=time.time() + delay, src=src, offset=0.0)
    threading.Thread(target=_player, args=(src, title, ev, delay), daemon=True).start()
    print(f'[music] playing {title!r} from {source}', flush=True)
    return {'ok': True, 'playing': title, 'source': source,
            'note': 'Say just one short line (e.g. "playing <title>") - the song starts in a few seconds. When Chintu says "Chinnu" the song pauses, you listen, then it continues.'}

def stop():
    _paused.clear()
    return _halt()

def _halt():
    with _lock:
        ev, ff = _cur.get('stop'), _cur.get('ffmpeg')
        was = _cur.get('title')
        if ev: ev.set()
        if ff:
            try: ff.kill()
            except Exception: pass
        _cur.update(title=None, source=None, stop=None, ffmpeg=None)
    if was: time.sleep(0.4)          # let the robot release the speaker
    return {'ok': True, 'stopped': was}

def status():
    return {'playing': _cur.get('title'), 'source': _cur.get('source'),
            'seconds': int(time.time() - _cur['started']) if _cur.get('title') and _cur.get('started') else 0}

def is_playing(): return bool(_cur.get('title'))


def pause():
    """Wake word heard: stop the audio but remember where we were, so the song can continue after the command."""
    if not _cur.get('title'): return {'ok': False}
    pos = _cur.get('offset', 0.0) + max(0.0, time.time() - (_cur.get('started') or time.time()))
    keep = {'src': _cur.get('src'), 'title': _cur.get('title'), 'source': _cur.get('source'), 'pos': pos}
    _halt()
    _paused.clear(); _paused.update(keep)
    print(f"[music] paused {keep['title']!r} at {int(pos)}s", flush=True)
    return {'ok': True, 'paused': keep['title']}

def resume_if_paused():
    """Called when the conversation is over: continue the paused song (unless it was stopped or replaced)."""
    if not _paused or _cur.get('title'): _paused.clear() if _cur.get('title') else None; return False
    p = dict(_paused); _paused.clear()
    ev = threading.Event()
    with _lock:
        _cur.update(title=p['title'], source=p['source'], stop=ev, started=time.time() + 0.5, src=p['src'], offset=p['pos'])
    threading.Thread(target=_player, args=(p['src'], p['title'], ev, 0.5, max(0.0, p['pos'] - 1.0)), daemon=True).start()
    print(f"[music] resumed {p['title']!r} at {int(p['pos'])}s", flush=True)
    return True
