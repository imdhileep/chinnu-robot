import shutil, time
fn = 'mobile.py'
s = open(fn, encoding='utf-8').read()
shutil.copy(fn, fn + '.bak_owner' + time.strftime('%H%M%S'))
card = ' <div class="card"><button id="ptt"'
assert s.count(card) == 1
s = s.replace(card,
 ' <div class="card"><h3>Who is talking? <span id="own" style="float:right;font-size:13px">...</span></h3>'
 '<div style="display:flex;gap:8px"><button style="flex:1;padding:12px" onclick="ownSet(\'unlock\')">&#128275; Its me (30 min)</button>'
 '<button style="flex:1;padding:12px" onclick="ownSet(\'lock\')">&#128274; Guest mode</button></div>'
 '<div style="font-size:12px;color:var(--muted);margin-top:6px">Guests get no memories, history, files or home control. Chinnu also unlocks when it sees your face.</div></div>\n'
 + card, 1)
js = 'async function act(n){'
assert s.count(js) == 1
s = s.replace(js,
 "async function ownGet(){try{const r=await (await fetch('/api/owner')).json();$('own').textContent=r.owner?('\\u{1F513} owner '+Math.ceil(r.seconds_left/60)+'m ('+r.how+')'):'\\u{1F512} guest'}catch(e){}}\n"
 "async function ownSet(a){await post('/api/owner/'+a);ownGet()}\nownGet();setInterval(ownGet,20000);\n" + js, 1)
s += '''

@router.get('/api/owner')
def api_owner():
    import owner; return owner.status()

@router.post('/api/owner/{act}')
def api_owner_set(act: str, minutes: int = 30):
    import owner
    return owner.unlock(min(max(minutes, 1), 240), 'phone') if act == 'unlock' else owner.lock()
'''
open(fn, 'w', encoding='utf-8').write(s); print('patched mobile.py')
