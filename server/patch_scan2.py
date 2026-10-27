import shutil, time
fn = 'brain.py'
s = open(fn, encoding='utf-8').read(); shutil.copy(fn, fn + '.bak_scan2' + time.strftime('%H%M%S'))
i = s.index('\ndef who_is_here_scan():')
s = s[:i] + '''
HFOV, VFOV = 62.0, 48.0          # approx camera field of view (deg)
_yaw_sign = [1]                  # learned: +1 if positive yaw moves the image the expected way

def _snap():
    import requests
    r = requests.get(robot.URL + "/snap.jpg", headers=robot.HDR, timeout=8)
    return r.content if r.ok and len(r.content) > 1000 else None

def _head(yaw, pitch):
    import requests
    yaw = max(-80, min(80, yaw)); pitch = max(-30, min(28, pitch))
    try: requests.post(robot.URL + "/head", headers=robot.HDR, params={"yaw": round(yaw), "roll": 0, "pitch": round(pitch), "speed": 90}, timeout=5)
    except Exception: pass
    return yaw, pitch

def _look(jpg):
    import faces, vision
    f = faces.identify(jpg); people = vision.detect(jpg, only={'person'})
    return f, people

def who_is_here_scan():
    """Find people: look straight, then sweep the head around the room. Uses YOLO person detection
    (works from the side / far away), turns the head to centre on the person, then checks the face."""
    import time as _t
    spots = [(0, 10), (35, 10), (-35, 10), (65, 10), (-65, 10), (0, 25)]
    found = None
    for yaw, pitch in spots:
        _head(yaw, pitch); _t.sleep(0.7)
        jpg = _snap()
        if not jpg: return {"ok": False, "error": "camera not available"}
        f, people = _look(jpg)
        if f.get("known"):
            found = {"faces": f["faces"], "known": f["known"], "persons": len(people), "yaw": yaw}; break
        if people:
            # centre the head on the biggest person, aiming at the upper body where the face is
            p = people[0]
            ty = p['box'][1] / 480.0 + 0.12      # rough face height in frame (0..1); refined below
            try:
                import cv2, numpy as np
                h = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR).shape[0]
                ty = (p['box'][1] + 0.15 * p['box'][3]) / h
            except Exception: pass
            for attempt in range(2):
                dyaw = (0.5 - p['cx']) * HFOV * _yaw_sign[0]
                dpitch = (0.5 - ty) * VFOV
                yaw, pitch = _head(yaw + dyaw, pitch + dpitch); _t.sleep(0.7)
                jpg = _snap() or jpg
                f, people2 = _look(jpg)
                if f.get("known") or not people2: break
                # if the person moved further from centre, our yaw direction is reversed - learn it
                if abs(people2[0]['cx'] - 0.5) > abs(p['cx'] - 0.5) + 0.05: _yaw_sign[0] *= -1
                p = people2[0]
            found = {"faces": f.get("faces", []), "known": f.get("known", []), "persons": max(1, len(people)), "yaw": yaw,
                     "note": None if f.get("known") else "a person is visible (body detected) but the face is not clear enough to recognise - maybe turned away or too far"}
            if f.get("known"): break
    if found is None:
        _head(0, 0)
        found = {"faces": [], "known": [], "persons": 0, "note": "looked all around the room (left, right, up) - no person visible"}
    found["ok"] = True
    if found.get("persons"): found["direction"] = "left" if found.get("yaw", 0) * _yaw_sign[0] > 15 else "right" if found.get("yaw", 0) * _yaw_sign[0] < -15 else "in front"
    try:
        import owner
        st = owner.status()
        found["speaker_verified_as_owner"] = bool(st.get("owner")); found["verified_by"] = st.get("how") or "not verified"
        if st.get("owner") and st.get("how") == "voice":
            found["note_voice"] = "The speaker's VOICE matches Chintu (voice ID) even if the face is not visible."
    except Exception: pass
    return found

def what_objects():
    """Quick local object list from the robot camera (YOLO, no cloud)."""
    import vision
    jpg = _snap()
    if not jpg: return {"ok": False, "error": "camera not available"}
    objs = vision.detect(jpg)
    return {"ok": True, "summary": vision.summary(objs), "objects": [{k: o[k] for k in ("name", "conf", "cx")} for o in objs[:15]]}
'''
# register a quick object tool
tool = '''  {"type": "function", "function": {
    "name": "detect_objects",
    "description": "Fast on-device object detection from your camera: lists the objects and people in front of you (person, laptop, cup, chair, phone, bottle, tv, ...). Use for 'em em vunnayi', 'enni', 'is there a ...?' questions. For detailed descriptions use look.",
    "parameters": {"type": "object", "properties": {}}}},
'''
anchor = '  {"type": "function", "function": {\n    "name": "who_is_here"'
assert s.count(anchor) == 1
s = s.replace(anchor, tool + anchor)
a2 = '        if name == "who_is_here":\n'
s = s.replace(a2, '        if name == "detect_objects":\n            return what_objects()\n' + a2, 1)
open(fn, 'w', encoding='utf-8').write(s); print('ok')
