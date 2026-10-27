"""Custom commands for Chinnu, defined by Chintu in commands.yaml (reloaded on every call)."""
import os, time, subprocess, yaml, requests
import robot, home

CMD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'commands.yaml')
SHELL_TIMEOUT = 20

def load():
    try:
        return yaml.safe_load(open(CMD_FILE, encoding='utf-8')) or {}
    except Exception as e:
        return {'_error': str(e)}

def names():
    return [k for k in load().keys() if not k.startswith('_')]

def describe():
    cmds = load()
    return '; '.join(f"'{k}'" + (f" ({v.get('description')})" if isinstance(v, dict) and v.get('description') else '')
                     for k, v in cmds.items() if not k.startswith('_')) or '(none defined yet)'

def _step(step):
    parts = str(step).split()
    if not parts: return {'ok': False, 'error': 'empty step'}
    kind = parts[0].lower()
    try:
        if kind == 'light' and len(parts) >= 3:
            return home.light(parts[1], parts[2], parts[3] if len(parts) > 3 else None)
        if kind == 'lights' and len(parts) >= 2:
            return {'ok': True, 'results': home.all_lights(parts[1], parts[2] if len(parts) > 2 else None)}
        if kind == 'robot' and len(parts) >= 2:
            return robot.action(parts[1])
        if kind == 'volume' and len(parts) >= 2:
            p = {'mute': 'on'} if parts[1] == 'mute' else ({'mute': 'off'} if parts[1] == 'unmute' else {'percent': int(parts[1])})
            r = requests.post(f'{robot.URL}/volume', headers=robot.HDR, params=p, timeout=5)
            return r.json() if r.ok else {'ok': False, 'error': r.text}
        if kind == 'speak':
            import voice
            return voice.say(' '.join(parts[1:]))
        if kind == 'brain':   # ask the GPT brain (tools allowed) and speak its reply
            import voice, brain
            prompt = ' '.join(parts[1:])
            reply = brain.chat(prompt)
            try: requests.post('http://127.0.0.1:8080/state', json={'chat': {'who': 'Chinnu', 'text': reply}}, timeout=2)
            except Exception: pass
            voice.say(reply)
            return {'ok': True, 'reply': reply}
        if kind == 'plug' and len(parts) >= 3:     # plug <govee socket / group, may have spaces> on|off
            import govee_plug
            return govee_plug.set_plug(' '.join(parts[1:-1]), parts[-1].lower() == 'on')
        if kind == 'strip' and len(parts) >= 3:    # strip <1|2|3|usb|friendly name> on|off
            import tuya_strip
            return tuya_strip.set_outlet(' '.join(parts[1:-1]), parts[-1].lower() == 'on')
        if kind in ('guard', 'follow') and len(parts) >= 2:
            return requests.post(f'http://127.0.0.1:8080/api/{kind}/{parts[1]}', timeout=10).json()
        if kind == 'sleep':
            time.sleep(float(parts[1])); return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}
    return {'ok': False, 'error': f'unknown step: {step}'}

def run(name):
    cmds = load()
    key = next((k for k in cmds if k.lower() == (name or '').lower().strip()), None)
    if key is None:
        key = next((k for k in cmds if (name or '').lower() in k.lower()), None)
    if key is None:
        return {'ok': False, 'error': f'no command named {name}', 'available': names()}
    spec = cmds[key] or {}
    out = {'ok': True, 'command': key, 'steps': [], 'say': spec.get('say')}
    for s in spec.get('steps') or []:
        out['steps'].append({'step': s, 'result': _step(s)})
    if spec.get('shell'):
        try:
            env = dict(os.environ)
            r = subprocess.run(spec['shell'], shell=True, capture_output=True, text=True, timeout=SHELL_TIMEOUT, env=env)
            out['shell_output'] = (r.stdout + r.stderr).strip()[-1500:]
            out['shell_exit'] = r.returncode
        except Exception as e:
            out['ok'] = False; out['shell_error'] = str(e)
    return out


def scheduled():
    """Commands that carry a schedule: {name: {'at': 'HH:MM', 'days': [...]}}"""
    out = {}
    for k, v in load().items():
        if k.startswith('_') or not isinstance(v, dict) or not v.get('schedule'):
            continue
        sch = v['schedule']
        if isinstance(sch, str):
            sch = {'at': sch}
        if sch.get('enabled', True) and sch.get('at'):
            out[k] = {'at': str(sch['at']), 'days': [str(d).lower()[:3] for d in sch.get('days', [])]}
    return out
