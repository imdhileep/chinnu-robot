d = open('dashboard.py', encoding='utf-8').read()
if '/api/move/' not in d:
    old = "@app.post('/api/chat')"
    new = '''@app.post('/api/move/{direction}')
def move(direction: str, ms: int = 700):
    """Continuous movement keepalive (remote control hold buttons)."""
    try:
        r = requests.post(f'{ROBOT}/move/{direction}', headers=HDR, params={'ms': ms}, timeout=5)
        return r.json()
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.post('/api/chat')'''
    assert old in d; d = d.replace(old, new, 1)
    # dashboard D-pad: hold -> keepalive every 300 ms, release -> /move/stop
    d = d.replace("function holdStart(a){holdA=a;fire();holdT=setInterval(fire,900)}",
                  "const MV={step_forward:'forward',step_backward:'backward',step_left:'turn_left',step_right:'turn_right'};function holdStart(a){holdA=MV[a]||a;fire();holdT=setInterval(fire,300)}", 1)
    d = d.replace("async function fire(){if(!holdA)return;try{await fetch('/api/action/'+holdA,{method:'POST'})}catch(e){}}",
                  "async function fire(){if(!holdA)return;try{await fetch('/api/move/'+holdA,{method:'POST'})}catch(e){}}", 1)
    d = d.replace("function holdStop(){clearInterval(holdT);holdT=null;holdA=null}",
                  "function holdStop(){clearInterval(holdT);holdT=null;if(holdA)fetch('/api/move/stop',{method:'POST'});holdA=null}", 1)
    open('dashboard.py', 'w', encoding='utf-8').write(d); print('dashboard ok')

m = open('mobile.py', encoding='utf-8').read()
if '/api/move/' not in m:
    old = "let holdT=null,holdA=null;function holdStart(a){holdA=a;fire();holdT=setInterval(fire,900)}async function fire(){if(holdA)post('/api/action/'+holdA)}function holdStop(){clearInterval(holdT);holdT=null;holdA=null}"
    new = "const MV={step_forward:'forward',step_backward:'backward',step_left:'turn_left',step_right:'turn_right'};let holdT=null,holdA=null;function holdStart(a){holdA=MV[a]||a;fire();holdT=setInterval(fire,300)}async function fire(){if(holdA)post('/api/move/'+holdA)}function holdStop(){clearInterval(holdT);holdT=null;if(holdA)post('/api/move/stop');holdA=null}"
    assert old in m; m = m.replace(old, new, 1)
    open('mobile.py', 'w', encoding='utf-8').write(m); print('mobile ok')
