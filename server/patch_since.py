p = 'uptime.py'; s = open(p).read()
helper = '''
def _real_since(k, now):
    """First time we see a feature: use the real start time for services/containers."""
    f = next((f for f in FEATURES if key_of(f) == k), None)
    try:
        if f and f[2] == 'unit':
            us = _sh(['systemctl', 'show', f[3], '-p', 'ActiveEnterTimestampMonotonic', '--value'])
            if us and us != '0': return now - (time.monotonic() - int(us) / 1e6)
        if f and f[2] == 'docker':
            from datetime import datetime
            st = _sh(['docker', 'inspect', '-f', '{{.State.StartedAt}}', f[3]])[:19]
            if st: return datetime.strptime(st, '%Y-%m-%dT%H:%M:%S').replace(tzinfo=__import__('datetime').timezone.utc).timestamp()
        if f and f[2] in ('self', 'loop'):
            return now - (time.monotonic() - _PROC_START)
    except Exception: pass
    return now
_PROC_START = time.monotonic()
'''
s = s.replace('\ndef _load_state():', helper + '\ndef _load_state():', 1)
old = "                _cur[k] = {'ok': ok, 'note': note, 'since': now}"
new = "                _cur[k] = {'ok': ok, 'note': note, 'since': _real_since(k, now) if (old is None and ok) else now}"
assert s.count(old) == 1; s = s.replace(old, new)
open(p, 'w').write(s); print('ok')
