"""Chinnu activity log + history page (/history) + daily summary.
log(kind, text, **extra) appends to logs/chinnu-YYYY-MM-DD.jsonl. Included by dashboard.py."""
import os, json, time, glob
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
BASE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE, 'logs'); os.makedirs(LOG_DIR, exist_ok=True)

def log(kind, text, **extra):
    try:
        rec = {'t': time.strftime('%H:%M:%S'), 'kind': kind, 'text': str(text)[:2000], **extra}
        with open(os.path.join(LOG_DIR, time.strftime('chinnu-%Y-%m-%d.jsonl')), 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except Exception as e:
        print('[history] log failed', e, flush=True)

def read(day=None, q=None, kinds=None, limit=500):
    day = day or time.strftime('%Y-%m-%d')
    p = os.path.join(LOG_DIR, f'chinnu-{day}.jsonl')
    out = []
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            try: r = json.loads(line)
            except Exception: continue
            if kinds and r.get('kind') not in kinds: continue
            if q and q.lower() not in json.dumps(r, ensure_ascii=False).lower(): continue
            out.append(r)
    return out[-limit:]

def days():
    return sorted([os.path.basename(p)[7:17] for p in glob.glob(os.path.join(LOG_DIR, 'chinnu-*.jsonl'))], reverse=True)

@router.get('/api/history')
def api_history(day: str = None, q: str = None, kind: str = None):
    return {'day': day or time.strftime('%Y-%m-%d'), 'days': days(), 'items': read(day, q, [kind] if kind else None)}

def summary_text(day=None):
    """Ask the brain model for a short Telugu (roman) summary of the day's log."""
    items = read(day, limit=400)
    if not items: return None
    counts = {}
    for r in items: counts[r['kind']] = counts.get(r['kind'], 0) + 1
    lines = [f"{r['t']} [{r['kind']}] {r['text']}" for r in items if r['kind'] in ('chintu', 'chinnu', 'command', 'action', 'photo', 'record', 'reminder', 'schedule', 'alert')][-150:]
    try:
        from openai import OpenAI
        import yaml
        cfg = yaml.safe_load(open(os.path.join(BASE, 'config.yaml'), encoding='utf-8'))
        model = cfg['brain']['model']
        resp = OpenAI().chat.completions.create(model=model, messages=[
            {'role': 'system', 'content': "You are Chinnu, a playful robot dog. Summarize today's activity log for your owner Chintu in Telugu written in English letters (roman Telugu, with English tech words), max 5 short sentences, warm and a little funny. Mention counts (conversations, commands, photos) and anything notable (alerts, reminders). No lists, no markdown."},
            {'role': 'user', 'content': f"Counts: {counts}\nLog:\n" + '\n'.join(lines)}], max_completion_tokens=300)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Ivala {counts.get('chintu', 0)} conversations, {counts.get('command', 0) + counts.get('action', 0)} commands, {counts.get('photo', 0)} photos anna. (summary error: {e})"

@router.get('/api/summary')
def api_summary(day: str = None):
    return {'ok': True, 'day': day or time.strftime('%Y-%m-%d'), 'summary': summary_text(day)}

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Chinnu history</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>
:root{--bg:#0b0f1a;--card:#10162a;--fg:#e8ecf4;--muted:#8a93a8;--accent:#4cc9f0}
*{box-sizing:border-box;margin:0;padding:0}body{background:var(--bg);color:var(--fg);font-family:-apple-system,system-ui,Roboto,sans-serif;padding:12px;padding-top:calc(12px + env(safe-area-inset-top))}
a{color:var(--accent);text-decoration:none}#top{display:flex;gap:12px;align-items:center;margin-bottom:10px;flex-wrap:wrap}h1{font-size:18px;flex:1}
select,input,button{font-size:14px;padding:9px 10px;border-radius:10px;border:1px solid #1b2440;background:#0e1424;color:var(--fg)}button{background:#1f2a48;border:0;font-weight:600}
.item{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #1b2440;font-size:15px;line-height:1.35}.item .t{color:var(--muted);font-size:12px;width:56px;flex:none;padding-top:3px}
.k{font-size:11px;padding:2px 7px;border-radius:8px;background:#1b2440;color:var(--muted);flex:none;height:fit-content;margin-top:2px}
.chintu .k{background:#1b2440}.chinnu .k{background:#163a3a;color:#9fe}.action .k,.command .k{background:#3a3516;color:#fd9}.alert .k{background:#5a2030;color:#fbb}.photo .k,.record .k{background:#2a2050;color:#cbf}
#sum{background:var(--card);border-radius:14px;padding:12px;margin:8px 0;font-size:15px;line-height:1.4;display:none}
</style></head><body>
<div id="top"><a href="/m">&larr; Chinnu</a><h1>History</h1><select id="day"></select><input id="q" placeholder="search..." style="width:140px"><button onclick="load()">Go</button><button onclick="summary()">Summary</button></div>
<div id="sum"></div><div id="list"></div>
<script>
const $=id=>document.getElementById(id);
async function load(){const d=$('day').value;const q=$('q').value;const r=await (await fetch('/api/history?day='+(d||'')+'&q='+encodeURIComponent(q))).json();
if(!$('day').options.length){r.days.forEach(x=>{const o=document.createElement('option');o.value=x;o.textContent=x;$('day').appendChild(o)});$('day').value=r.day}
$('list').innerHTML=r.items.length?r.items.slice().reverse().map(i=>'<div class="item '+i.kind+'"><span class="t">'+i.t.slice(0,5)+'</span><span class="k">'+i.kind+'</span><span>'+esc(i.text)+'</span></div>').join(''):'<div class="item"><span>nothing logged</span></div>'}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')}
async function summary(){$('sum').style.display='block';$('sum').textContent='Chinnu thinking...';const r=await (await fetch('/api/summary?day='+$('day').value)).json();$('sum').textContent=r.summary||'nothing today'}
$('q').addEventListener('keydown',e=>{if(e.key==='Enter')load()});$('day').addEventListener('change',load);load();
</script></body></html>"""

@router.get('/history', response_class=HTMLResponse)
def history_page():
    return PAGE
