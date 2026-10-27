import shutil
B = '/home/dk/chinnu-agent/'
for f in ('motioncam.py', 'dashboard.py', 'mobile.py'): shutil.copy(B + f, B + f + '.bak_motvid')

s = open(B + 'motioncam.py').read()
s = s.replace('"""Motion camera: whenever Chinnu\'s camera sees movement, take a photo.',
              '"""Motion camera: whenever Chinnu\'s camera sees movement, take a photo AND record a 30 s video clip (mp4, same name).', 1)
s = s.replace("import os, json, time, threading, shutil, pathlib, requests",
              "import os, json, time, threading, shutil, pathlib, requests, subprocess\nCLIP_SECS = 30\n_rec = {'proc': None}", 1)
# start a clip next to the photo
old = "                    p = _save(jpg); t_save = time.time()\n"
assert old in s
s = s.replace(old, old + "                    _start_clip(p.with_suffix('.mp4'))\n", 1)
# helper functions before _loop
anchor = "def _loop():"
s = s.replace(anchor, '''def _recording():
    p = _rec['proc']; return p is not None and p.poll() is None

def _start_clip(path):
    """Record CLIP_SECS of the robot camera into path (skipped if a clip is already running)."""
    if _recording(): return
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'mjpeg', '-r', '8', '-i', f'{ROBOT}/camera', '-t', str(CLIP_SECS),
           '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28', '-pix_fmt', 'yuv420p', '-r', '8', '-movflags', '+faststart', str(path)]
    try:
        _rec['proc'] = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _st['last_video'] = time.strftime('%I:%M:%S %p')
    except Exception as e: print('[motion] video', e, flush=True)

''' + anchor, 1)
s = s.replace("nextcloud_sync.sync_dir(str(ROOT / time.strftime('%Y-%m-%d')), sub='motion', exts=('.jpg',))",
              "nextcloud_sync.sync_dir(str(ROOT / time.strftime('%Y-%m-%d')), sub='motion', exts=('.jpg', '.mp4'))", 1)
# recent(): mark items that have a video
old_r = "            out.append({'day': d.name, 'file': f.name, 't': f'{f.name[:2]}:{f.name[2:4]}:{f.name[4:6]}'})"
assert old_r in s
s = s.replace(old_r, "            v = f.with_suffix('.mp4')\n            out.append({'day': d.name, 'file': f.name, 't': f'{f.name[:2]}:{f.name[2:4]}:{f.name[4:6]}',\n                        'video': v.name if v.exists() and not (_recording() and time.time() - v.stat().st_mtime < 3) else None})", 1)
s = s.replace("    return {**cfg(), **_st, 'today': len(list(d.glob('*.jpg'))) if d.exists() else 0}",
              "    return {**cfg(), **_st, 'today': len(list(d.glob('*.jpg'))) if d.exists() else 0,\n            'videos_today': len(list(d.glob('*.mp4'))) if d.exists() else 0, 'recording': _recording()}", 1)
open(B + 'motioncam.py', 'w').write(s)

d = open(B + 'dashboard.py').read()
d += """

# motion clips (mp4) served with range support so iPhone Safari can play them
try:
    from fastapi.staticfiles import StaticFiles as _SF
    import pathlib as _pl
    _pl.Path('/mnt/hdd/chinnu/motion').mkdir(parents=True, exist_ok=True)
    app.mount('/motion/files', _SF(directory='/mnt/hdd/chinnu/motion'), name='motionfiles')
except Exception as _e: print('[motion] mount', _e)
"""
open(B + 'dashboard.py', 'w').write(d)

m = open(B + 'mobile.py', encoding='utf-8').read()
a = "$('mgrid').innerHTML=r.items.length?r.items.map(x=>'<a href=\"/api/motion/img/'+x.day+'/'+x.file+'\" target=\"_blank\" style=\"text-decoration:none\">"
assert a in m
m = m.replace(a, "$('mgrid').innerHTML=r.items.length?r.items.map(x=>'<a href=\"'+(x.video?'/motion/files/'+x.day+'/'+x.video:'/api/motion/img/'+x.day+'/'+x.file)+'\" target=\"_blank\" style=\"text-decoration:none;position:relative;display:block\">'+(x.video?'<span style=\"position:absolute;top:4px;left:4px;background:#000a;color:#fff;border-radius:6px;padding:1px 6px;font-size:11px\">&#9654; video</span>':'')+'", 1)
b = "$('mstat').textContent=(MS.on?'ON':'off')+' · '+MS.today+' today'"
assert b in m
m = m.replace(b, "$('mstat').textContent=(MS.on?'ON':'off')+' · '+MS.today+' photos, '+(MS.videos_today||0)+' videos today'+(MS.recording?' · \\u{1F534} REC':'')", 1)
m = m.replace('Chinnu takes a photo whenever its camera sees movement. Saved to the hard disk + Nextcloud (30 days).',
              'Chinnu takes a photo + records a 30 s video whenever its camera sees movement. Saved on the server hard disk + Nextcloud (30 days). Tap a tile to play.', 1)
open(B + 'mobile.py', 'w', encoding='utf-8').write(m)
print('patched')
