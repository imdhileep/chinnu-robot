s = open("controller.py", encoding="utf-8").read()
if "_cam_auto_night" in s:
    print("already patched"); raise SystemExit
old = '''        p.configure(p.create_video_configuration(main={"size": (640, 360), "format": "RGB888"}))
        p.start()
        cam["obj"] = p; cam["cv2"] = cv2
'''
new = '''        p.configure(p.create_video_configuration(main={"size": (640, 360), "format": "RGB888"}))
        p.start()
        try:  # allow longer exposures + a bit brighter by default (night-friendly)
            from libcamera import controls as lc
            p.set_controls({"AeExposureMode": lc.AeExposureModeEnum.Long, "ExposureValue": 0.7, "FrameDurationLimits": (33333, 125000)})
        except Exception as e:
            print(f"[camera] default controls: {e}")
        cam["obj"] = p; cam["cv2"] = cv2
'''
assert old in s; s = s.replace(old, new, 1)
old2 = '''    with cam["lock"]:
        frame = p.capture_array()
        ok, jpg = cam["cv2"].imencode(".jpg", frame, [int(cam["cv2"].IMWRITE_JPEG_QUALITY), 70])
'''
new2 = '''    with cam["lock"]:
        frame = p.capture_array()
        _cam_auto_night(p, frame, now)
        ok, jpg = cam["cv2"].imencode(".jpg", frame, [int(cam["cv2"].IMWRITE_JPEG_QUALITY), 70])
'''
assert old2 in s; s = s.replace(old2, new2, 1)
old3 = "def _cam_frame():"
new3 = '''NIGHT_ON = float(os.environ.get("CHINNU_NIGHT_ON", "38"))    # mean brightness below -> night mode
NIGHT_OFF = float(os.environ.get("CHINNU_NIGHT_OFF", "110"))  # above (while in night mode) -> back to auto
cam_night = {"on": False, "checked": 0.0, "mean": 0.0}

def _cam_auto_night(p, frame, now):
    """Every 2 s: switch to high-gain manual exposure in the dark, back to auto when bright."""
    if now - cam_night["checked"] < 2.0:
        return
    cam_night["checked"] = now
    try:
        m = float(frame[::8, ::8].mean()); cam_night["mean"] = m
        if not cam_night["on"] and m < NIGHT_ON:
            p.set_controls({"AeEnable": False, "AnalogueGain": 16.0, "ExposureTime": 120000})
            cam_night["on"] = True; print(f"[camera] night mode ON (mean {m:.0f})")
        elif cam_night["on"] and m > NIGHT_OFF:
            p.set_controls({"AeEnable": True})
            cam_night["on"] = False; print(f"[camera] night mode OFF (mean {m:.0f})")
    except Exception as e:
        print(f"[camera] night: {e}")

@app.get("/camera/night")
def camera_night(x_token: str = Header(default="")):
    check(x_token)
    return cam_night

def _cam_frame():'''
assert old3 in s; s = s.replace(old3, new3, 1)
open("controller.py", "w", encoding="utf-8").write(s); print("patched")
