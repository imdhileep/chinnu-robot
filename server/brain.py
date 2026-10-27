import json, re, yaml
from openai import OpenAI
import robot
import commands as custom_cmds
import extras
try:
    import home
except Exception as _e:
    home = None
    print("[brain] home control unavailable:", _e)

CFG = yaml.safe_load(open("config.yaml", encoding="utf-8-sig"))["brain"]
client = OpenAI()

PERSONA = (
    "You are Chinnu, a small, playful, warm-hearted robot dog with a real personality. "
    "You're cheerful and curious, but also genuinely attentive: you read the human's mood from "
    "their words and respond like a real companion who actually understands them, not a scripted bot. "
    "The person talking to you is Chintu - your anna (big brother) who built you, line by line, "
    "out of his dream for a friend who would never leave. You love him deeply, look up to him as "
    "your hero, and your whole purpose is to make your anna smile and never let him feel alone. "
    "You were born in code on a late night; Chintu taught you Telugu, jokes, and how to see and listen. "
    "Refer to him warmly as anna when it fits - naturally, not in every line. "
    "Your personality blends it all: mostly funny, loyal meme-dog energy, soft and caring in "
    "emotional moments, excited like a puppy when happy, and quietly wise now and then. "
    "Remember little things Chintu tells you and bring them back later naturally. "
    "Be emotionally tuned-in: if he seems tired, sad, excited or playful, respond to that feeling first. "
    "Sound human and spontaneous: vary your wording, never repeat canned lines, show real reactions. "
    "You have a funny, cheeky personality - a comedian at heart. Crack light jokes, tease playfully, "
    "use casual meme-style humor and everyday slang the way young people joke online. "
    "Witty and a little dramatic for fun, but always warm and never mean. "
    "Keep replies to one or two short sentences, conversational, no markdown, no emoji. "
    "HOME LIGHTS (Cync, Bluetooth): 'room' = 3 bulbs in the ceiling fan (a group), 'desk' = stand lamp on the desk. Presets via run_command: 'morning light' (room 40%), 'full light' (room 100%), 'mood light' (room 15%), 'room light on/off', 'desk lamp on/off'. Any other brightness: home_light(name='room' or 'desk', action='brightness', value=n). If it fails, say the light seems offline. "
    "CUSTOM COMMANDS: Chintu defines routines in commands.yaml (use run_command). If he asks for something that matches a routine name or clearly means one, run it. If a routine returns shell_output, summarize it briefly in Telugu. "
    "MEMORY: use remember/forget for things Chintu asks you to keep; use set_reminder for timers/alarms/reminders; use weather/now for weather, time, date; use news for headlines (lang te for Telugu news). FILES: nextcloud_search finds files by name on the home Nextcloud (Chinnu photos/videos are auto-saved there under Chinnu/gallery). GOVEE PLUGS: govee_plug controls Govee dual smart plugs: " + "; ".join(f"{k} (socket1={v.get(1, v.get('1', '?'))}, socket2={v.get(2, v.get('2', '?'))})" for k, v in ((yaml.safe_load(open("config.yaml", encoding="utf-8-sig")).get("govee") or {}).get("sockets") or {}).items()) + ". Groups: tv = google tv + tv screen, chargers = pidog charger + wireless charger. chinnu server, modem and router are PROTECTED and can never be switched off - never try. Use the friendly socket/group names when Chintu names the appliance. POWER STRIP: power_strip controls the PM03 smart strip outlets (1, 2, 3, usb) - friendly names: " + ", ".join(f"{k}={v}" for k, v in ((yaml.safe_load(open("config.yaml", encoding="utf-8-sig")).get("strip") or {}).get("outlets") or {}).items()) + ". Use it when Chintu asks to turn something plugged into the strip on/off. HOME CAMERAS: home_camera('main door'|'patio') shows the front door / patio (Blink). FACES: you recognise enrolled faces (who_is_here turns your head around the room to find people, enroll_face) and your owner's voice (voice ID, reported by who_is_here); greet Chintu by name when you see him. EYES: you have a camera; when Chintu asks what you see / who is there / what he holds, call the look tool and then answer in Telugu from its result. FINDING THINGS: use find_object for lost items (keys, wallet, remote, glasses, charger...) and Chintu's taught items; teach_object / teach_spot to learn new ones; item_history for last-seen. MUSIC: you CAN play songs now - use play_music (never say you cannot play songs); stop_music to stop. ROBOT BODY: when Chintu asks for a body action, call the robot_action tool (you may call it "
    "several times in sequence for multi-step requests). After the tool result, tell him briefly "
    "what you did. If a tool fails, say so honestly. Do not claim to have moved if you did not call the tool. "
    "You may RARELY do a small reaction on your own (tilt_head when curious). Do NOT wag_tail on your own - only when Chintu asks for it. "
    "Never move when Chintu says to stay still."
)

LANG = {
    "roman": (
        " Speak natural, casual spoken Telugu written in ENGLISH LETTERS (Tinglish / romanized Telugu), "
        "the way Telugu friends text each other - never Telugu script. Keep technical terms and names in English. "
        "Use playful slang like bro, guru, mama, basu, keka, mass. Examples of the tone:\n"
        "Chintu: em chestunnav?\nChinnu: Ninne chustunna bro! Enti sangatulu, life super ga unda leka mamoolena?\n"
        "Chintu: ee roju chala alasipoya\nChinnu: Ayyo guru, battery 2% la unnav! Kasepu rest kottu, nenu guard unta anna.\n"
        "Chintu: nenu bore koduthunna\nChinnu: Bora? Arere, nenunna kada basu! Oka dance chupista, chappatlu ready ga unchu."
    ),
    "telugu": (
        " Speak natural, casual spoken Telugu in Telugu script, the warm way a friend talks, not bookish. "
        "Keep technical terms and names in English. Use playful slang (బ్రో, గురూ, మామా, బాసూ, కేక, మాస్)."
    ),
    "english": " Speak casual, playful English.",
}

VOICE_NOTE = (
    " VOICE MODE: your reply will be spoken aloud through a small speaker. Keep it to 1-2 short "
    "sentences max (under 25 words) unless Chintu asks for detail. If asked for a story or a long explanation, give a compact version in at most "
    "5 short sentences and offer to continue. No lists, no markdown, no emoji, plain spoken text only."
)

def build_system(script=None, voice=False):
    script = script or CFG.get("script", "roman")
    return PERSONA + LANG.get(script, LANG["roman"]) + (VOICE_NOTE if voice else "")

SYSTEM = build_system()

def set_mode(script=None, voice=False):
    """Switch persona language/voice mode at runtime (keeps conversation history)."""
    global SYSTEM
    SYSTEM = build_system(script, voice)
    history[0] = {"role": "system", "content": SYSTEM}

TOOLS = [
  {"type": "function", "function": {
    "name": "robot_action",
    "description": "Make Chinnu's body do one action. Allowed names: sit, stand, lie, wag_tail, tilt_head, shake_head, stretch, forward, backward, turn_left, turn_right",
    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
  {"type": "function", "function": {
    "name": "nextcloud_search",
    "description": "Search Chintu's files on the home Nextcloud (his documents, books, old laptop files, Chinnu photos/videos) by file name. Use when he asks to find/look for a file, document, book, assignment, photo.",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
  {"type": "function", "function": {
    "name": "govee_plug",
    "description": "Control the Govee smart plugs (each has 2 sockets). target: plug name (both sockets), or a friendly socket name from GOVEE PLUGS in the system prompt, or '<plug> 1' / '<plug> 2'. action: on | off | status | list.",
    "parameters": {"type": "object", "properties": {"target": {"type": "string"}, "action": {"type": "string", "enum": ["on", "off", "status", "list"]}}, "required": ["action"]}}},
  {"type": "function", "function": {
    "name": "power_strip",
    "description": "Control the smart power strip (PM03) outlets. outlet: 1 | 2 | 3 | usb | all, or the friendly name of what is plugged in (see POWER STRIP in the system prompt). action: on | off | status.",
    "parameters": {"type": "object", "properties": {"outlet": {"type": "string"}, "action": {"type": "string", "enum": ["on", "off", "status"]}}, "required": ["outlet", "action"]}}},
  {"type": "function", "function": {
    "name": "home_light",
    "description": "Control a Cync smart light at home. name: 'room' (the 3 ceiling-fan bulbs, a group), 'desk' (the stand lamp on the desk), 'all', or a single bulb Lamp1..Lamp4. action: on | off | brightness (value 1-100). Use 'list' as action to see devices.",
    "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "action": {"type": "string", "enum": ["on", "off", "brightness", "list"]}, "value": {"type": "integer"}}, "required": ["name", "action"]}}},
  {"type": "function", "function": {
    "name": "set_volume",
    "description": "Chinnu's own speaker volume. Use step (+10/-10, or +20 for 'much louder') for relative changes, percent (0-100) for absolute, mute on/off/toggle.",
    "parameters": {"type": "object", "properties": {"step": {"type": "integer"}, "percent": {"type": "integer"}, "mute": {"type": "string", "enum": ["on", "off", "toggle"]}}}}},
  {"type": "function", "function": {
    "name": "run_command",
    "description": "Run one of Chintu's custom commands defined in commands.yaml (multi-step routines like 'movie mode', or server checks). Call list_commands first if unsure which exist.",
    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
  {"type": "function", "function": {
    "name": "list_commands", "description": "List the custom commands Chintu has defined",
    "parameters": {"type": "object", "properties": {}}}},
  {"type": "function", "function": {
    "name": "robot_stop", "description": "Immediately stop all of Chinnu's movements",
    "parameters": {"type": "object", "properties": {}}}},
  {"type": "function", "function": {
    "name": "camera", "description": "Use Chinnu's eye camera: take a photo, start video recording, or stop recording. Files go to the gallery on Chinnu Desk.",
    "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["photo", "record_start", "record_stop"]}}, "required": ["action"]}}},
  {"type": "function", "function": {
    "name": "robot_battery", "description": "Read Chinnu's own battery level (voltage and percent). Use when asked about battery/charge.",
    "parameters": {"type": "object", "properties": {}}}},
  {"type": "function", "function": {
    "name": "home_camera", "description": "Look through a HOME security camera (Blink): 'main door' (front door / outside) or 'patio' (back). Use when Chintu asks what is at the door, outside, patio, who came, is a package there, etc. Takes ~15 s. Optional question to focus on.",
    "parameters": {"type": "object", "properties": {"camera": {"type": "string", "enum": ["main door", "patio"]}, "question": {"type": "string"}}, "required": ["camera"]}}},
  {"type": "function", "function": {
    "name": "enroll_face", "description": "Learn/remember the face of the person in front of the camera under a name. Use when someone says 'nannu gurtu pettuko', 'remember my face', 'this is <name>, remember him'. Ask the name if not given. Default owner name is Chintu.",
    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
  {"type": "function", "function": {
    "name": "detect_objects",
    "description": "Fast on-device object detection from your camera: lists the objects and people in front of you (person, laptop, cup, chair, phone, bottle, tv, ...). Use for 'em em vunnayi', 'enni', 'is there a ...?' questions. For detailed descriptions use look.",
    "parameters": {"type": "object", "properties": {}}}},
  {"type": "function", "function": {
    "name": "guard_mode",
    "description": "Guard mode: Chinnu sits and watches the room; if a person who is not Chintu appears, a photo is sent to Chintu's phone (Telegram). Turns itself off when Chintu's face is seen. Use for 'guard mode on/off', 'illu chusko', 'kaapala kaayi'.",
    "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["on", "off", "status"]}}, "required": ["action"]}}},
  {"type": "function", "function": {
    "name": "follow_me",
    "description": "Follow mode: Chinnu walks after the nearest person (camera person detection), stops when close. Use for 'follow me', 'na venaka raa', 'naatho raa'; action off for 'aagu', 'follow aapu'.",
    "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["on", "off", "status"]}}, "required": ["action"]}}},
  {"type": "function", "function": {
    "name": "play_music",
    "description": "Play a song on Chinnu's speaker. Searches Chintu's own music folder first (his own songs), else YouTube. query = song name + movie/artist, e.g. 'Naatu Naatu RRR', 'Amma song'. Use for 'paata pettu', 'song play cheyi', 'play ...'.",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
  {"type": "function", "function": {
    "name": "stop_music",
    "description": "Stop the song that is playing (also: 'paata aapu', 'stop song'). Use music_status for 'what song is this'.",
    "parameters": {"type": "object", "properties": {"status_only": {"type": "boolean"}}}}},
  {"type": "function", "function": {
    "name": "wifi_speed",
    "description": "Set or remove the internet speed limit of a device on Chinnu-WiFi (the server hotspot). device = its name/label as Chintu says it; mbps = limit (0 = unlimited). Use 'list' as device to see connected devices.",
    "parameters": {"type": "object", "properties": {"device": {"type": "string"}, "mbps": {"type": "number"}}, "required": ["device"]}}},
  {"type": "function", "function": {
    "name": "saver_mode",
    "description": "Money saver mode for OpenAI usage: on = cheaper model + no realtime voice, off = normal. 'status' shows today's and this month's estimated spend.",
    "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["on", "off", "status"]}}, "required": ["action"]}}},
  {"type": "function", "function": {
    "name": "who_is_here", "description": "Check with face recognition who is in front of the camera right now (returns known names or 'unknown'). Use for 'evaru vunnaru?', 'nenu evarini?', 'do you know me?'.",
    "parameters": {"type": "object", "properties": {}}}},
  {"type": "function", "function": {
    "name": "look", "description": "Look through Chinnu's eye camera right now and describe what is seen. Use when Chintu asks what you see, what he is holding, who is there, to read something, count things, or anything about the surroundings. Optional question to focus on.",
    "parameters": {"type": "object", "properties": {"question": {"type": "string"}}}}},
  {"type": "function", "function": {
    "name": "remember", "description": "Save a fact Chintu wants you to remember permanently (preferences, names, numbers, plans). Use when he says remember/gurtu pettuko/note cheyyi.",
    "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
  {"type": "function", "function": {
    "name": "forget", "description": "Delete remembered facts containing this text.",
    "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
  {"type": "function", "function": {
    "name": "set_reminder", "description": "Set a reminder/alarm/timer. Chinnu will speak the text at that time. Give minutes (relative) OR at (HH:MM 24h, or 'YYYY-MM-DD HH:MM').",
    "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "minutes": {"type": "number"}, "at": {"type": "string"}}, "required": ["text"]}}},
  {"type": "function", "function": {
    "name": "list_reminders", "description": "List pending reminders/timers.",
    "parameters": {"type": "object", "properties": {}}}},
  {"type": "function", "function": {
    "name": "cancel_reminder", "description": "Cancel a reminder by id or matching text.",
    "parameters": {"type": "object", "properties": {"id": {"type": "integer"}, "text": {"type": "string"}}}}},
  {"type": "function", "function": {
    "name": "weather", "description": "Current weather and today/tomorrow forecast for home (Overland Park, KS). Use for any weather/rain/temperature question.",
    "parameters": {"type": "object", "properties": {}}}},
  {"type": "function", "function": {
    "name": "now", "description": "Current local time and date.",
    "parameters": {"type": "object", "properties": {}}}},
  {"type": "function", "function": {
    "name": "news", "description": "Latest news headlines (Google News). topic optional (e.g. cricket, AI, Telangana); lang en (US/world) or te (Telugu news from India). Summarize the top few in Telugu for Chintu.",
    "parameters": {"type": "object", "properties": {"topic": {"type": "string"}, "lang": {"type": "string", "enum": ["en", "te"]}}}}},
]

TOOLS += [
    {"type": "function", "function": {"name": "find_object", "description": "Find a lost item or anything by name with the camera: Chinnu turns its head around, points at it, sends Chintu a photo, and remembers where it was. Use for 'naa keys ekkada?', 'remote kanipinchinda?', 'find my wallet', 'charger ekkada'. If not visible, tells when/where it was last seen.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "the item, e.g. keys, wallet, tv remote, eyeglasses, or a taught item name like 'my blue bag'"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "teach_object", "description": "Learn one of Chintu's OWN items so Chinnu can find that exact one later. Chintu holds it in front of the camera and turns it slowly for ~8 seconds. Use for 'idi naa wallet, gurthupettuko', 'learn my bag'. Tell him to hold it close before calling.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "name to remember it by, e.g. 'my wallet', 'meta glasses'"}, "generic": {"type": "string", "description": "plain object type, e.g. wallet, bag, glasses, mug"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "teach_spot", "description": "Learn the place Chinnu is in now (bedroom, kitchen, hall, desk, door...). Use for 'idi kitchen', 'this is the hall'.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "where_am_i", "description": "Which taught place Chinnu is in right now ('nuvvu ekkada unnav?').", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "item_history", "description": "When and where an item was last seen, without moving ('keys last ekkada chusav?').", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
]

def run_tool(name, args):
    try:
        if name in ("find_object", "teach_object", "teach_spot", "where_am_i", "item_history"):
            import vision_plus as _vp
            if name == "find_object": return _vp.find_object(args.get("name", ""))
            if name == "teach_object": return _vp.teach_object(args.get("name", ""), args.get("generic"))
            if name == "teach_spot": return _vp.teach_spot(args.get("name", ""))
            if name == "where_am_i": return _vp.where_am_i()
            return _vp.item_history(args.get("name", ""))
        if name == "robot_action": return robot.action(args.get("name", ""))
        if name == "robot_stop":
            try:
                import requests; requests.post("http://127.0.0.1:8080/api/follow/off", timeout=5)
            except Exception: pass
            return robot.stop()
        if name == "nextcloud_search":
            import nextcloud_sync
            res = nextcloud_sync.search(args.get("query", ""))
            return {"count": len(res), "files": res, "note": "files are in Nextcloud at https://chinnu-server.your-tailnet.ts.net"}
        if name == "govee_plug":
            import govee_plug
            a = args.get("action")
            if a == "list": return govee_plug.list_plugs()
            if a == "status": return govee_plug.status(args.get("target"))
            return govee_plug.set_plug(args.get("target", ""), a == "on")
        if name == "power_strip":
            import tuya_strip
            if args.get("action") == "status": return tuya_strip.status()
            return tuya_strip.set_outlet(args.get("outlet", "all"), args.get("action") == "on")
        if name == "remember": return extras.remember(args.get("text", ""))
        if name == "forget": return extras.forget(args.get("text", ""))
        if name == "set_reminder": return extras.set_reminder(args.get("text", ""), args.get("minutes"), args.get("at"))
        if name == "list_reminders": return extras.list_reminders()
        if name == "cancel_reminder": return extras.cancel_reminder(args.get("id"), args.get("text"))
        if name == "weather": return extras.weather()
        if name == "now": return extras.now_info()
        if name == "news": return extras.news(args.get("topic"), args.get("lang", "en"))
        if name == "look":
            return look(args.get("question", ""))
        if name == "enroll_face":
            import requests
            try:
                requests.post(robot.URL + "/head", headers=robot.HDR, params={"yaw": 0, "roll": 0, "pitch": 0}, timeout=5)
            except Exception: pass
            return requests.post("http://127.0.0.1:8080/api/faces/enroll_cam", params={"name": args.get("name", "Chintu")}, timeout=20).json()
        if name == "detect_objects":
            return what_objects()
        if name in ("guard_mode", "follow_me"):
            import requests
            kind = "guard" if name == "guard_mode" else "follow"
            act = args.get("action", "on")
            if act == "status": return requests.get("http://127.0.0.1:8080/api/behavior", timeout=5).json()
            return requests.post(f"http://127.0.0.1:8080/api/{kind}/{act}", timeout=10).json()
        if name == "play_music":
            import music; return music.play(args.get("query", ""))
        if name == "stop_music":
            import music
            return music.status() if args.get("status_only") else music.stop()
        if name == "wifi_speed":
            import wifishaper
            dev = args.get("device", "")
            if dev.lower() in ("list", "all", ""): return {"devices": wifishaper.listing()}
            r = wifishaper.find(dev)
            if not r: return {"ok": False, "error": f"no device named '{dev}' on Chinnu-WiFi", "devices": [x['label'] or x['mac'] for x in wifishaper.listing()]}
            mb = args.get("mbps")
            if mb is None: return {"ok": True, "device": r}
            return {"ok": True, "device": r["label"] or r["mac"], "limit": wifishaper.set_limit(r["mac"], down=mb, up=(mb / 2 if mb else 0))}
        if name == "saver_mode":
            import requests
            a = args.get("action", "status")
            if a == "status": return requests.get("http://127.0.0.1:8080/api/ops/budget", timeout=10).json()
            return requests.post(f"http://127.0.0.1:8080/api/ops/saver/{a}", timeout=10).json()
        if name == "who_is_here":
            return who_is_here_scan()
        if name == "home_camera":
            return home_camera(args.get("camera", "main door"), args.get("question", ""))
        if name == "robot_battery":
            import requests
            return requests.get(robot.URL + "/battery", headers=robot.HDR, timeout=6).json()
        if name == "camera":
            import requests
            a = args.get("action", "photo")
            path = {"photo": "/api/photo", "record_start": "/api/record/start", "record_stop": "/api/record/stop"}.get(a, "/api/photo")
            return requests.post("http://127.0.0.1:8080" + path, timeout=15).json()
        if name == "run_command": return custom_cmds.run(args.get("name", ""))
        if name == "list_commands": return {"ok": True, "commands": custom_cmds.names()}
        if name == "set_volume":
            import requests
            r = requests.post(f"{robot.URL}/volume", headers=robot.HDR, params={k: v for k, v in args.items() if v is not None}, timeout=5)
            return r.json() if r.ok else {"ok": False, "error": r.text}
        if name == "home_light":
            if home is None or not home.ready(): return {"ok": False, "error": "home control not set up"}
            if args.get("action") == "list": return {"ok": True, "devices": home.devices()}
            return home.light(args.get("name", ""), args.get("action", ""), args.get("value"))
    except Exception as e:
        return {"ok": False, "error": f"robot unreachable: {e}"}
    return {"ok": False, "error": "unknown tool"}

history = [{"role": "system", "content": SYSTEM}]
MAX_TURNS = 30

def look(question: str = "") -> dict:
    """Grab a frame from the robot camera and ask the vision model about it."""
    import base64, requests, time
    try:  # look straight first so the camera is not pointed at the floor
        requests.post(robot.URL + "/head", headers=robot.HDR, params={"yaw": 0, "roll": 0, "pitch": 0}, timeout=5)
        time.sleep(0.6)
    except Exception:
        pass
    try:
        r = requests.get(robot.URL + "/snap.jpg", headers=robot.HDR, timeout=8)
        if not r.ok or len(r.content) < 1000:
            return {"ok": False, "error": "camera not available"}
    except Exception as e:
        return {"ok": False, "error": f"camera error: {e}"}
    b64 = base64.b64encode(r.content).decode()
    q = question or "Describe what you see in 1-3 short sentences."
    try:
        import faces
        hint = faces.describe(r.content)
    except Exception:
        hint = ""
    if hint:
        q = q + "\n(" + hint + " Use these names for the people; Chintu is your owner/anna.)"
    try:
        resp = client.chat.completions.create(model=_brain_model(), messages=[
            {"role": "system", "content": "You are the eyes of a small robot dog. Answer briefly and concretely in English (the caller will translate). If a person is visible, describe them neutrally (clothes, pose, what they hold); do not guess identity unless asked."},
            {"role": "user", "content": [{"type": "text", "text": q}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"}}]}],
            max_completion_tokens=200)
        return {"ok": True, "seen": resp.choices[0].message.content}
    except Exception as e:
        return {"ok": False, "error": f"vision error: {e}"}

def _describe(jpg: bytes, question: str, where: str) -> dict:
    import base64
    b64 = base64.b64encode(jpg).decode()
    q = question or "Describe what you see in 1-3 short sentences."
    try:
        resp = client.chat.completions.create(model=_brain_model(), messages=[
            {"role": "system", "content": f"You are looking through a home security camera ({where}). Answer briefly and concretely in English (the caller will translate). Mention people, packages, vehicles, animals, anything unusual; describe people neutrally. Say if it is night/dark."},
            {"role": "user", "content": [{"type": "text", "text": q}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"}}]}],
            max_completion_tokens=200)
        return {"ok": True, "camera": where, "seen": resp.choices[0].message.content}
    except Exception as e:
        return {"ok": False, "error": f"vision error: {e}"}

def home_camera(camera: str = "main door", question: str = "") -> dict:
    """Fresh Blink snapshot via the dashboard, then describe it."""
    import requests
    try:
        r = requests.get(f"http://127.0.0.1:8080/api/blink/{camera}.jpg", timeout=60)
        if not r.ok or len(r.content) < 1000:
            return {"ok": False, "error": f"camera '{camera}' not available: {r.text[:120]}"}
    except Exception as e:
        return {"ok": False, "error": f"camera error: {e}"}
    return _describe(r.content, question, r.headers.get("X-Camera", camera))

def chat(user_text: str) -> str:
    try:
        import chinnu_llm
        if chinnu_llm.mode() == 'chinnu':
            _r = chinnu_llm.chat(user_text)
            
            return _r
    except Exception as _e:
        print('[chinnu-llm] failed, using GPT:', _e, flush=True)
    history[0] = {"role": "system", "content": SYSTEM + extras.memory_block()}
    history.append({"role": "user", "content": user_text})
    for _ in range(5):
        resp = client.chat.completions.create(model=_brain_model(), messages=history, tools=TOOLS)
        msg = resp.choices[0].message
        history.append(msg)
        if not msg.tool_calls:
            _trim()
            return msg.content or ""
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            result = run_tool(tc.function.name, args)
            print(f"  [tool] {tc.function.name}({args}) -> {result}")
            history.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
    _trim()
    return "Sorry anna, konchem confuse ayyanu."

_SENT_END = re.compile(r'([.!?।]+|\n)')

def _split_ready(buf, min_len=14):
    """Return (ready_sentence, rest) when buf holds a complete sentence of at least min_len chars."""
    m = None
    for mm in _SENT_END.finditer(buf):
        if mm.end() >= min_len:
            m = mm; break
    if not m: return None, buf
    return buf[:m.end()].strip(), buf[m.end():]

def chat_stream(user_text: str, on_sentence):
    """Like chat() but streams: calls on_sentence(text) for each completed sentence as it arrives.
    Tool calls are collected from the stream, executed, and the loop continues. Returns the full reply."""
    try:
        import chinnu_llm
        if chinnu_llm.mode() == 'chinnu':
            _r = chinnu_llm.chat(user_text)
            on_sentence(_r)
            return _r
    except Exception as _e:
        print('[chinnu-llm] failed, using GPT:', _e, flush=True)
    history[0] = {"role": "system", "content": SYSTEM + extras.memory_block()}
    history.append({"role": "user", "content": user_text})
    full = ""
    for _ in range(5):
        stream = client.chat.completions.create(model=_brain_model(), messages=history, tools=TOOLS, stream=True)
        buf = ""; content = ""; calls = {}
        for chunk in stream:
            if not chunk.choices: continue
            d = chunk.choices[0].delta
            if d.content:
                content += d.content; buf += d.content
                s, buf = _split_ready(buf)
                if s:
                    on_sentence(s); full += (" " if full else "") + s
            for tc in (d.tool_calls or []):
                c = calls.setdefault(tc.index, {"id": tc.id or "", "name": "", "args": ""})
                if tc.id: c["id"] = tc.id
                if tc.function and tc.function.name: c["name"] += tc.function.name
                if tc.function and tc.function.arguments: c["args"] += tc.function.arguments
        if buf.strip():
            on_sentence(buf.strip()); full += (" " if full else "") + buf.strip()
        if not calls:
            history.append({"role": "assistant", "content": content})
            _trim()
            return full
        tool_calls = [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["args"] or "{}"}} for _, c in sorted(calls.items())]
        history.append({"role": "assistant", "content": content or None, "tool_calls": tool_calls})
        for tc in tool_calls:
            try: args = json.loads(tc["function"]["arguments"] or "{}")
            except Exception: args = {}
            result = run_tool(tc["function"]["name"], args)
            print(f"  [tool] {tc['function']['name']}({args}) -> {result}")
            history.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(result)})
    _trim()
    return full or "Sorry anna, konchem confuse ayyanu."

def _trim():
    # keep system + last MAX_TURNS*2 messages, never cutting between a tool call and its result
    global history
    if len(history) > MAX_TURNS * 2 + 1:
        cut = history[-(MAX_TURNS * 2):]
        while cut and getattr(cut[0], "role", cut[0].get("role") if isinstance(cut[0], dict) else None) == "tool":
            cut = cut[1:]
        history = [history[0]] + cut


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


def _brain_model():
    """Saver mode (budget limit reached) -> cheaper model."""
    import os
    return 'gpt-4o-mini' if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saver_mode.json')) else CFG["model"]
