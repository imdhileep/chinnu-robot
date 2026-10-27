import shutil
P = '/home/dk/chinnu-agent/nextcloud_sync.py'
shutil.copy(P, P + '.bak_nccp')
s = open(P).read()
old = s[s.index("def push(path, sub='gallery'):"):s.index("def push_async")]
new = '''def push(path, sub='gallery', scan=True):
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

'''
s = s.replace(old, new, 1)
old2 = s[s.index("def sync_dir("):s.index("def search(")]
new2 = '''def sync_dir(directory, sub='gallery', exts=('.jpg', '.mp4')):
    """Push every file in a folder that has not been pushed yet, then index the folder once."""
    n = 0
    for f in sorted(pathlib.Path(directory).glob('*')):
        if f.suffix.lower() in exts and f'{sub}/{f.name}' not in _pushed() and push(f, sub, scan=False): n += 1
    if n: _scan(sub)
    return n

'''
s = s.replace(old2, new2, 1)
open(P, 'w').write(s)
print('patched')
