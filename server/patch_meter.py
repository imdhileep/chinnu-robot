import shutil, time
ts = time.strftime('%H%M%S')
def bak(fn): shutil.copy(fn, fn + '.bak_meter' + ts)

# 1) usage meter is installed wherever voice.py is imported (all processes use it)
fn = 'voice.py'; s = open(fn, encoding='utf-8').read()
if 'usage.install()' not in s:
    bak(fn)
    s = s.replace('\n_tts_client = ', '\ntry:\n    import usage; usage.install()\nexcept Exception as _e: print("[usage]", _e)\n_tts_client = ', 1)
    open(fn, 'w', encoding='utf-8').write(s); print('voice ok')

# 2) realtime: record token usage of every response
fn = 'realtime.py'; s = open(fn, encoding='utf-8').read()
if 'usage.record' not in s:
    bak(fn)
    a = "            elif t == 'response.done':\n"
    assert s.count(a) == 1
    s = s.replace(a, a + '''                try:
                    u = (ev.get('response') or {}).get('usage') or {}
                    ind, outd = u.get('input_token_details') or {}, u.get('output_token_details') or {}
                    import usage
                    usage.record('realtime', MODEL, text_in=ind.get('text_tokens', 0) - (ind.get('cached_tokens', 0) or 0),
                                 cached_in=ind.get('cached_tokens', 0) or 0, audio_in=ind.get('audio_tokens', 0),
                                 text_out=outd.get('text_tokens', 0), audio_out=outd.get('audio_tokens', 0))
                except Exception as _e: print('[usage]', _e, flush=True)
''')
    open(fn, 'w', encoding='utf-8').write(s); print('realtime ok')

# 3) device usage log (who switched what, when)
WRAP = '''

# ---- device usage log (server page: lights & accessories timeline) ----
def _devlog(fn_name, label_fn):
    import functools, sys, os
    orig = globals()[fn_name]
    @functools.wraps(orig)
    def w(*a, **kw):
        r = orig(*a, **kw)
        try:
            import history
            name, on = label_fn(*a, **kw)
            src = os.environ.get('CHINNU_SRC') or os.path.basename(sys.argv[0] or '?')
            history.log('device', f"{name} {'ON' if on else 'OFF'}", device=str(name), on=bool(on), src=src,
                        ok=bool(r.get('ok', True)) if isinstance(r, dict) else True)
        except Exception as e: print('[devlog]', e, flush=True)
        return r
    globals()[fn_name] = w
'''
for fn, call in [('govee_plug.py', "_devlog('set_plug', lambda target, on, *a, **k: (target, on))"),
                 ('tuya_strip.py', "_devlog('set_outlet', lambda outlet, on, *a, **k: ('strip ' + str(outlet), on))"),
                 ('home.py', "_devlog('light', lambda name, action, *a, **k: (f'light {name}' + (f' {a[0]}%' if action == 'brightness' and a and a[0] else ''), action != 'off'))")]:
    s = open(fn, encoding='utf-8').read()
    if '_devlog(' not in s:
        bak(fn); s += WRAP + call + '\n'
        open(fn, 'w', encoding='utf-8').write(s); print(fn, 'ok')

# 4) autocharge: the max-hours safety must apply even when the robot is unreachable
fn = 'autocharge.py'; s = open(fn, encoding='utf-8').read()
if 'safety (robot offline)' not in s:
    bak(fn)
    a = "    if v is None:\n"
    s = s.replace(a, '''    if on and s.get('on_since') and (now - s['on_since']) / 3600 > c['max_hours']:
        if _set(False):
            _log(f"safety stop after {(now - s['on_since']) / 3600:.1f} h - charger OFF" + (" (robot offline)" if v is None else ""))
            s['on_since'] = None; s['full_hits'] = 0; s['charger_on'] = False
        _save(s); return
''' + a, 1)
    open(fn, 'w', encoding='utf-8').write(s); print('autocharge ok')
