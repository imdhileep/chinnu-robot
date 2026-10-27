import shutil, time
fn = 'brain.py'
s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_scan' + time.strftime('%H%M%S'))
old = '''        if name == "who_is_here":
            import requests
            try:
                requests.post(robot.URL + "/head", headers=robot.HDR, params={"yaw": 0, "roll": 0, "pitch": 0}, timeout=5)
            except Exception: pass
            r = requests.get("http://127.0.0.1:8080/api/faces/identify", timeout=20).json()
            if not r.get("faces"): r["note"] = "no face visible"
            return r
'''
new = '''        if name == "who_is_here":
            return who_is_here_scan()
'''
assert s.count(old) == 1
s = s.replace(old, new)
s += '''

def who_is_here_scan():
    """Look straight first; if nobody is visible, turn the head around the room (left/right/up)
    until a face is found, and keep looking at that person. Also reports the voice-ID result."""
    import requests, time as _t
    spots = [(0, 10), (35, 10), (-35, 10), (65, 10), (-65, 10), (0, 25), (35, 25), (-35, 25)]
    names = {0: 'straight', 35: 'left', -35: 'right', 65: 'far left', -65: 'far right'}
    best = None
    for yaw, pitch in spots:
        try:
            requests.post(robot.URL + "/head", headers=robot.HDR, params={"yaw": yaw, "roll": 0, "pitch": pitch, "speed": 90}, timeout=5)
        except Exception: pass
        _t.sleep(0.8)
        try:
            r = requests.get("http://127.0.0.1:8080/api/faces/identify", timeout=20).json()
        except Exception as e:
            return {"ok": False, "error": str(e)}
        if r.get("faces"):
            r["looked"] = names.get(yaw, f"yaw {yaw}")
            best = r
            if r.get("known"): break           # found someone we know - stop and keep looking at them
    if best is None:
        try: requests.post(robot.URL + "/head", headers=robot.HDR, params={"yaw": 0, "roll": 0, "pitch": 0}, timeout=5)
        except Exception: pass
        best = {"ok": True, "faces": [], "known": [], "note": "looked all around the room (left, right, up) - no face visible"}
    try:
        import owner
        st = owner.status()
        best["speaker_verified_as_owner"] = bool(st.get("owner"))
        best["verified_by"] = st.get("how") or "not verified"
        if st.get("owner") and st.get("how") == "voice":
            best["note_voice"] = "The speaker's VOICE matches Chintu (voice ID) even if the face is not visible."
    except Exception: pass
    return best
'''
# tell the model about it
s = s.replace("FACES: you recognise enrolled faces (who_is_here, enroll_face);",
              "FACES: you recognise enrolled faces (who_is_here turns your head around the room to find people, enroll_face) and your owner's voice (voice ID, reported by who_is_here);", 1)
open(fn, 'w', encoding='utf-8').write(s); print('ok')
