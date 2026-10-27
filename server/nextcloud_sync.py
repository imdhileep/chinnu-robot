"""Chinnu <-> Nextcloud (same server, docker 'nextcloud-app-1').
push(path, sub): copy a gallery file into Nextcloud  /Chinnu/<sub>/  and index it.
search(query):   find files by name in the user's Nextcloud (incl. the Old laptop share)."""
import os, json, pathlib, subprocess, threading

CONTAINER = 'nextcloud-app-1'
NC_USER = 'dk'
ROOT = f'/var/www/html/data/{NC_USER}/files'
DONE = pathlib.Path.home() / '.chinnu_nc_pushed.json'
_lock = threading.Lock()

def _run(args, timeout=120):
    return subprocess.run(['sudo', '-n', 'docker'] + args, capture_output=True, text=True, timeout=timeout)

def _pushed():
    try: return set(json.load(open(DONE)))
    except Exception: return set()

def push(path, sub='gallery', scan=True):
    """Copy one file into Nextcloud (streamed via docker exec - docker cp can't write into the nested data mount)."""
    p = pathlib.Path(path)
    if not p.exists() or p.stat().st_size == 0: return False
    key = f'{sub}/{p.name}'
    with _lock:
        done = _pushed()
        if key in done: return True
        dest = f'{ROOT}/Chinnu/{sub}'
        _run(['exec', '-u', 'www-data', CONTAINER, 'mkdir', '-p', dest])
        with open(p, 'rb') as fh:
            r = subprocess.run(['sudo', '-n', 'docker', 'exec', '-i', '-u', 'www-data', CONTAINER, 'sh', '-c', f'cat > "{dest}/{p.name}"'],
                               stdin=fh, capture_output=True, timeout=120)
        if r.returncode != 0: print('[nextcloud] copy failed', r.stderr[:200], flush=True); return False
        if scan: _scan(sub)
        done.add(key); json.dump(sorted(done), open(DONE, 'w'))
    print(f'[nextcloud] pushed {key}', flush=True)
    return True

def _scan(sub):
    _run(['exec', '-u', 'www-data', CONTAINER, 'php', 'occ', 'files:scan', '--path', f'/{NC_USER}/files/Chinnu/{sub}', '-q'], timeout=600)

def push_async(path, sub='gallery'):
    threading.Thread(target=push, args=(path, sub), daemon=True).start()

def sync_dir(directory, sub='gallery', exts=('.jpg', '.mp4')):
    """Push every file in a folder that has not been pushed yet, then index the folder once."""
    n = 0
    for f in sorted(pathlib.Path(directory).glob('*')):
        if f.suffix.lower() in exts and f'{sub}/{f.name}' not in _pushed() and push(f, sub, scan=False): n += 1
    if n: _scan(sub)
    return n

def search(query, limit=12):
    """Case-insensitive filename search across the user's files and the Old laptop share."""
    q = str(query).strip()
    if not q: return []
    out = []
    for base, label in ((ROOT, ''), ('/mnt/old-laptop', 'Old laptop/')):
        r = _run(['exec', CONTAINER, 'sh', '-c', f'find {base} -iname "*{q}*" -not -path "*/node_modules/*" 2>/dev/null | head -{limit}'], timeout=60)
        for line in r.stdout.splitlines():
            rel = line.replace(base + '/', '', 1)
            out.append(label + rel)
            if len(out) >= limit: return out
    return out
