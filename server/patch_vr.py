import shutil, time
fn = 'mobile.py'
s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_vr' + time.strftime('%H%M%S'))
if "'/vr'" not in s:
    s += '''

@router.get('/vr', response_class=HTMLResponse)
def vr_page():
    import pathlib
    return pathlib.Path(__file__).with_name('vr.html').read_text(encoding='utf-8')
'''
open(fn, 'w', encoding='utf-8').write(s); print('patched')
