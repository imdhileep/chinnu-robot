p = 'brain.py'; s = open(p).read()
tools = '''
TOOLS += [
    {"type": "function", "function": {"name": "find_object", "description": "Find a lost item or anything by name with the camera: Chinnu turns its head around, points at it, sends Chintu a photo, and remembers where it was. Use for 'naa keys ekkada?', 'remote kanipinchinda?', 'find my wallet', 'charger ekkada'. If not visible, tells when/where it was last seen.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "the item, e.g. keys, wallet, tv remote, eyeglasses, or a taught item name like 'my blue bag'"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "teach_object", "description": "Learn one of Chintu's OWN items so Chinnu can find that exact one later. Chintu holds it in front of the camera and turns it slowly for ~8 seconds. Use for 'idi naa wallet, gurthupettuko', 'learn my bag'. Tell him to hold it close before calling.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "name to remember it by, e.g. 'my wallet', 'meta glasses'"}, "generic": {"type": "string", "description": "plain object type, e.g. wallet, bag, glasses, mug"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "teach_spot", "description": "Learn the place Chinnu is in now (bedroom, kitchen, hall, desk, door...). Use for 'idi kitchen', 'this is the hall'.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "where_am_i", "description": "Which taught place Chinnu is in right now ('nuvvu ekkada unnav?').", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "item_history", "description": "When and where an item was last seen, without moving ('keys last ekkada chusav?').", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
]
'''
anchor = '\ndef run_tool(name, args):\n'
if 'find_object' not in s:
    assert s.count(anchor) == 1
    s = s.replace(anchor, tools + anchor, 1)
    s = s.replace('def run_tool(name, args):\n    try:\n', '''def run_tool(name, args):
    try:
        if name in ("find_object", "teach_object", "teach_spot", "where_am_i", "item_history"):
            import vision_plus as _vp
            if name == "find_object": return _vp.find_object(args.get("name", ""))
            if name == "teach_object": return _vp.teach_object(args.get("name", ""), args.get("generic"))
            if name == "teach_spot": return _vp.teach_spot(args.get("name", ""))
            if name == "where_am_i": return _vp.where_am_i()
            return _vp.item_history(args.get("name", ""))
''', 1)
    s = s.replace("MUSIC: you CAN play songs now", "FINDING THINGS: use find_object for lost items (keys, wallet, remote, glasses, charger...) and Chintu's taught items; teach_object / teach_spot to learn new ones; item_history for last-seen. MUSIC: you CAN play songs now", 1)
open(p, 'w').write(s)

p = 'dashboard.py'; s = open(p).read()
if 'vision_plus' not in s:
    s += '''

if not os.environ.get('CHINNU_LAN'):
    import vision_plus; vision_plus.start()

@app.get('/api/vision_plus')
def api_vision_plus():
    import vision_plus; return vision_plus.status()

@app.post('/api/vision_plus/find')
def api_vp_find(name: str):
    import vision_plus; return vision_plus.find_object(name)
'''
open(p, 'w').write(s)

p = 'owner.py'; s = open(p).read()   # guests may NOT use the camera-search tools (privacy)
print('patched')
