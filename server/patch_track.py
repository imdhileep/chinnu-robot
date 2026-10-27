c = open('config.yaml', encoding='utf-8-sig').read()
if 'track:' not in c:
    c = c.replace("  face_interval: 20", "  face_interval: 20\n  track: true             # head follows the nearest face (server-side, ~3 fps)\n  track_hz: 3\n  track_yaw_sign: -1      # flip to 1 if the head turns the wrong way\n  track_pitch_sign: 1", 1)
    open('config.yaml', 'w', encoding='utf-8').write(c); print('config ok')

v = open('voice_agent.py', encoding='utf-8').read()
if 'def track_thread' not in v:
    v = v.replace('def heartbeat_thread():', '''track_state = {'yaw': 0.0, 'pitch': 0.0, 'seen': 0.0, 'active': False}

def track_thread():
    """Keep the head pointed at the largest face (server-side detection on /snap.jpg)."""
    import faces
    time.sleep(35)
    hz = float(IDLE.get('track_hz', 3) or 3)
    ys = float(IDLE.get('track_yaw_sign', -1) or -1); ps = float(IDLE.get('track_pitch_sign', 1) or 1)
    while True:
        time.sleep(max(0.15, 1.0 / hz))
        try:
            if not IDLE.get('track') or _quiet_now() or idle_moving[0]:
                continue
            r = requests.get(robot.URL + '/snap.jpg', headers=robot.HDR, timeout=3)
            if not r.ok or len(r.content) < 500: continue
            img = faces._decode(r.content)
            H, W = img.shape[:2]
            fs = faces.detect(img)
            now = time.time()
            if len(fs) == 0:
                if track_state['active'] and now - track_state['seen'] > 6:
                    track_state.update(yaw=0.0, pitch=0.0, active=False)
                    requests.post(robot.URL + '/head', headers=robot.HDR, params={'yaw': 0, 'pitch': 0, 'roll': 0, 'speed': 30}, timeout=3)
                continue
            f = max(fs, key=lambda q: q[2] * q[3])
            dx = (f[0] + f[2] / 2) / W - 0.5; dy = (f[1] + f[3] / 2) / H - 0.5
            track_state['seen'] = now; track_state['active'] = True
            if abs(dx) < 0.06 and abs(dy) < 0.08: continue
            yaw = max(-80, min(80, track_state['yaw'] + ys * dx * 40))
            pitch = max(-35, min(28, track_state['pitch'] - ps * dy * 30))
            track_state.update(yaw=yaw, pitch=pitch)
            requests.post(robot.URL + '/head', headers=robot.HDR, params={'yaw': round(yaw, 1), 'pitch': round(pitch, 1), 'roll': 0, 'speed': 90}, timeout=3)
        except Exception as e:
            print('[track] error', e, flush=True); time.sleep(2)

def heartbeat_thread():''', 1)
    # idle_moving flag + skip 'look' while tracking
    v = v.replace("last_wake = [0.0]\n", "last_wake = [0.0]\nidle_moving = [False]\n", 1)
    v = v.replace("            pick = random.choice(['look', 'look', 'look', 'tilt_head', 'shake_head', 'stretch', 'wag_tail'])\n            if pick == 'look':",
                  "            pick = random.choice(['look', 'look', 'look', 'tilt_head', 'shake_head', 'stretch', 'wag_tail'])\n            if IDLE.get('track') and track_state['active'] and pick == 'look': pick = 'tilt_head'\n            idle_moving[0] = True\n            if pick == 'look':", 1)
    v = v.replace("            print('[idle]', pick, flush=True)\n        except Exception as e:\n            print('[idle] error', e, flush=True)",
                  "            print('[idle]', pick, flush=True)\n        except Exception as e:\n            print('[idle] error', e, flush=True)\n        finally:\n            idle_moving[0] = False", 1)
    v = v.replace("    threading.Thread(target=greet_thread, daemon=True).start()\n",
                  "    threading.Thread(target=greet_thread, daemon=True).start()\n    threading.Thread(target=track_thread, daemon=True).start()\n", 1)
    open('voice_agent.py', 'w', encoding='utf-8').write(v); print('voice ok')

st = open('settings.py', encoding='utf-8').read()
if "'track'" not in st:
    st = st.replace("    for k in ('enabled', 'greet', 'greet_unknown'):", "    for k in ('enabled', 'greet', 'greet_unknown', 'track'):", 1)
    st = st.replace("['greet_unknown','ask unknown faces','chk'],", "['greet_unknown','ask unknown faces','chk'],['track','head follows faces','chk'],", 1)
    st = st.replace("['enabled','greet','greet_unknown'].forEach(k=>b[k]=$('i_'+k).checked)", "['enabled','greet','greet_unknown','track'].forEach(k=>b[k]=$('i_'+k).checked)", 1)
    open('settings.py', 'w', encoding='utf-8').write(st); print('settings ok')
