import json, govee_plug as g
print('LOCKED', g.LOCKED)
for t in ['tv', 'chargers', 'chinnu server', 'router', 'modem', 'spectrum wifi', 'misev', 'tv screen']:
    socks = g._sockets_for(t)
    print(f'{t:15}', [(s[2], 'LOCKED' if s[2] in g.LOCKED else 'ok') for s in socks])
print(json.dumps(g.status()))
