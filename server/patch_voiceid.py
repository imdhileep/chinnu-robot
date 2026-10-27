import shutil, time
fn = 'voice_agent.py'
s = open(fn, encoding='utf-8').read()
shutil.copy(fn, fn + '.bak_voiceid' + time.strftime('%H%M%S'))
a = "    import realtime\n    is_owner = owner_mode()\n"
assert s.count(a) == 1
s = s.replace(a, '''    import realtime
    is_owner = owner_mode()
    try:                                         # voice ID: decides per turn when confident
        import speaker, owner as _ow
        t0 = time.time(); vname, vscore = speaker.verify(wav)
        print(f'[voiceid] {vname} {vscore} ({time.time() - t0:.2f}s)', flush=True)
        if vname == 'Chintu':
            is_owner = True
            if not _ow.is_owner() or _ow.status()['seconds_left'] < 15 * 60: _ow.unlock(15, 'voice')
        elif 0 < vscore < speaker.LOW:
            is_owner = False                     # clearly a different voice -> guest for this turn
    except Exception as e:
        print('[voiceid] error', e, flush=True)
''')
open(fn, 'w', encoding='utf-8').write(s); print('patched', fn)
