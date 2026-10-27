import shutil, time, re
ts = time.strftime('%H%M%S')
def bak(f): shutil.copy(f, f + '.bak_ops' + ts)

c = open('config.yaml', encoding='utf-8').read()
if '\nops:' not in c:
    c += '''
ops:                   # ops.py: budget guard, nightly report, auto-heal
  daily_usd: 2.0       # OpenAI estimate per day -> warn at 80%, saver mode at 100%
  monthly_usd: 30.0
  report_at: "22:00"   # nightly Telegram report
  heal: true           # auto-restart failed services / containers (max 3 per hour each)
'''
    open('config.yaml', 'w', encoding='utf-8').write(c); print('config ok')

s = open('dashboard.py', encoding='utf-8').read()
if 'import ops' not in s:
    bak('dashboard.py')
    s += '''
if not os.environ.get('CHINNU_LAN'):
    import ops; ops.start(ROBOT, HDR)

@app.get('/api/ops/budget')
def api_ops_budget():
    import ops; return ops.budget_check()

@app.post('/api/ops/saver/{act}')
def api_ops_saver(act: str):
    import ops; ops.set_saver(act == 'on', 'turned on by Chintu' if act == 'on' else ''); return {'saver': ops.saver_on()}

@app.get('/api/ops/battery')
def api_ops_battery(day: str = None):
    import ops; return ops.battery_series(day)

@app.get('/api/ops/report')
def api_ops_report(send: int = 0):
    import ops
    t = ops.report_text()
    if send: ops.tg(t)
    return {'text': t}
'''
    open('dashboard.py', 'w', encoding='utf-8').write(s); print('dashboard ok')

b = open('brain.py', encoding='utf-8').read()
if '_brain_model()' not in b:
    bak('brain.py')
    b = b.replace('model=CFG["model"]', 'model=_brain_model()')
    b += '''

def _brain_model():
    """Saver mode (budget limit reached) -> cheaper model."""
    import os
    return 'gpt-4o-mini' if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saver_mode.json')) else CFG["model"]
'''
    tool = '''  {"type": "function", "function": {
    "name": "saver_mode",
    "description": "Money saver mode for OpenAI usage: on = cheaper model + no realtime voice, off = normal. 'status' shows today's and this month's estimated spend.",
    "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["on", "off", "status"]}}, "required": ["action"]}}},
'''
    anchor = '  {"type": "function", "function": {\n    "name": "who_is_here"'
    b = b.replace(anchor, tool + anchor, 1)
    a2 = '        if name == "who_is_here":\n'
    b = b.replace(a2, '''        if name == "saver_mode":
            import requests
            a = args.get("action", "status")
            if a == "status": return requests.get("http://127.0.0.1:8080/api/ops/budget", timeout=10).json()
            return requests.post(f"http://127.0.0.1:8080/api/ops/saver/{a}", timeout=10).json()
''' + a2, 1)
    open('brain.py', 'w', encoding='utf-8').write(b); print('brain ok')

v = open('voice_agent.py', encoding='utf-8').read()
if '_rt_enabled()' not in v:
    bak('voice_agent.py')
    v = v.replace("if V.get('realtime', False):", "if _rt_enabled():")
    v = v.replace("def rt_turn(", '''def _rt_enabled():
    """Realtime voice unless saver mode (budget limit) is on."""
    return V.get('realtime', False) and not os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saver_mode.json'))

def rt_turn(''', 1)
    if '\nimport os' not in v and 'import os,' not in v and ', os' not in v.split('\n', 30)[0:30].__str__():
        v = 'import os\n' + v
    open('voice_agent.py', 'w', encoding='utf-8').write(v); print('voice_agent ok')

h = open('server.html', encoding='utf-8').read()
if 'id="budget"' not in h:
    h = h.replace(' <div class="card"><h2>Today by type</h2><table id="bykind"></table></div>\n</div>',
''' <div class="card"><h2>Today by type</h2><table id="bykind"></table></div>
</div>

<div class="grid">
 <div class="card"><h2>Budget guard</h2><div id="budget" class="muted">…</div>
  <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap"><button onclick="saver('on')">💰 Saver mode on</button><button onclick="saver('off')">Saver mode off</button><button onclick="sendReport()">📨 Send report now</button></div>
  <div class="muted" style="margin-top:6px">Limits are in config.yaml → ops (daily $2, monthly $30). Warn at 80%, saver mode at 100%.</div></div>
 <div class="card"><h2>PiDog battery today</h2><svg id="batt" viewBox="0 0 300 110" style="width:100%;height:130px"></svg><div class="muted" id="battnote"></div></div>
</div>''', 1)
    h = h.replace('function loadAll(){', '''async function loadBudget(){const b=await j('/api/ops/budget');$('budget').innerHTML=`Today <b>$${b.today.toFixed(2)}</b> / $${b.limits.daily_usd} · Month <b>$${b.month.toFixed(2)}</b> / $${b.limits.monthly_usd}<br>Saver mode: <b style="color:${b.saver?'var(--warn)':'var(--ok)'}">${b.saver?'ON':'off'}</b>`}
async function saver(a){await j('/api/ops/saver/'+a,{method:'POST'});toast('Saver mode '+a);loadBudget()}
async function sendReport(){const r=await j('/api/ops/report?send=1');toast('Report sent to Telegram')}
async function loadBatt(){const s=(await j('/api/ops/battery')).filter(x=>x.pct!=null);const g=$('batt');if(!s.length){g.innerHTML='<text x="10" y="55" fill="currentColor" font-size="10" opacity=".6">Logging every 10 min - first points soon</text>';return}
 const toX=t=>{const[h,m]=t.split(':').map(Number);return 20+(h*60+m)/1440*270},toY=p=>100-p*0.9;
 let grid='';for(const p of[0,50,100])grid+=`<line x1="20" x2="290" y1="${toY(p)}" y2="${toY(p)}" stroke="currentColor" opacity=".15"/><text x="0" y="${toY(p)+3}" font-size="8" fill="currentColor" opacity=".6">${p}%</text>`;
 for(const h of[0,6,12,18,24])grid+=`<text x="${20+h/24*270-6}" y="110" font-size="8" fill="currentColor" opacity=".6">${h}:00</text>`;
 const pts=s.map(x=>toX(x.t)+','+toY(x.pct)).join(' ');const ch=s.filter(x=>x.charging).map(x=>`<circle cx="${toX(x.t)}" cy="${toY(x.pct)}" r="1.6" fill="#fbbf24"/>`).join('');
 g.innerHTML=grid+`<polyline points="${pts}" fill="none" stroke="#4cc9f0" stroke-width="1.6"/>`+ch;$('battnote').textContent=`now ${s[s.length-1].pct}% (${s[s.length-1].v} V) · yellow dots = charger on`}
function loadAll(){loadBudget();loadBatt();''', 1)
    open('server.html', 'w', encoding='utf-8').write(h); print('page ok')
s = open('srvpage.py', encoding='utf-8').read()
s = s.replace("    ('Monthly budget alert', 'Telegram message when the estimated OpenAI spend passes a daily or monthly limit you choose.'),\n", "")
s = s.replace("    ('Battery health', 'Log the PiDog battery voltage every 10 min and chart it, so the auto-charge limits can be tuned from real data.'),\n", "")
s = s.replace("    ('Auto-heal', 'If a service fails 3 times, restart it and send a Telegram alert automatically.'),\n", "")
open('srvpage.py', 'w', encoding='utf-8').write(s)
