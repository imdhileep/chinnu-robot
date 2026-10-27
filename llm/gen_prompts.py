"""Step A: generate diverse things Chintu might say to Chinnu (user turns only).
Usage: python gen_prompts.py <scale>   (scale 1.0 = full set ~1200, 0.05 = pilot)"""
import os, sys, json, random, concurrent.futures as cf
from openai import OpenAI

client = OpenAI()
SCALE = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
OUT = sys.argv[2] if len(sys.argv) > 2 else 'data/prompts.jsonl'

STYLE = ("Chintu is a young Telugu software engineer in Kansas talking to Chinnu, his robot dog, by VOICE. "
         "Mix styles: ~45% Tinglish (Telugu in English letters, e.g. 'light off cheyyi ra'), ~35% Telugu script "
         "(e.g. 'రూమ్ లైట్ ఆఫ్ చెయ్యి'), ~20% casual English. Add some speech-to-text noise: missing words, "
         "wrong spellings, 'chinnu' sometimes misheard as 'chinna'/'chinnamma'. Vary length (2-25 words), mood, slang "
         "(bro, ra, mama, anna, basu). Never number the lines.")

CATS = {
  'lights': (120, "control lights: room light (3 bulbs in fan) and desk lamp on/off, brightness % levels, presets morning/full/mood light, all lights"),
  'plugs': (110, "smart plugs and strip: TV on/off, google tv, pidog charger, wireless charger, stand main light (strip outlet 2), usb strip lights, desktop PC power (outlet 3); also status questions like 'TV on lo unda?'"),
  'protected': (25, "trying to switch OFF the chinnu server, modem, router or internet (these are protected and must be refused politely)"),
  'volume': (40, "speaker volume up/down/mute/set to a percent"),
  'body': (120, "robot body actions: sit, stand, lie down, wag tail, stretch, shake head, tilt head, bark, walk forward/back, turn left/right, push up, dance, stop moving, combinations like 'kurcho tarvatha tail oopu'"),
  'info': (90, "time, date, weather, rain/umbrella, news headlines (Telugu or English news, topics like cricket, tech, AP politics), Chinnu's battery level"),
  'memory': (90, "ask Chinnu to remember facts (birthdays, where keys are, likes), forget things, set reminders/timers/alarms ('10 minutes lo gurthu chey', 'repu 7am ki'), list or cancel reminders"),
  'music': (60, "play songs (Telugu movie songs, artists like SPB, Thaman, Anirudh, devotional, lofi), stop/pause music, what's playing"),
  'vision': (90, "what do you see, who is here, what am I holding, is anyone at the main door / patio camera, find objects, count people, take a photo, start/stop recording video, enroll my face as Chintu"),
  'modes': (60, "guard mode on/off/status, follow me, stop following, saver mode, limit wifi speed of a device on Chinnu-WiFi (e.g. 'guest phone ki 5 mbps pettu'), list routines"),
  'routines': (60, "routine names: good morning, movie mode, movie off, work mode, good night, leaving home, im home, server status, pidog battery - said naturally ('movie chuddam ra set chey', 'padukuntunna')"),
  'chat': (230, "everyday chit-chat with Chinnu: how are you, jokes, boredom, feeling tired/sad/happy/stressed about work or job search, food, cricket, movies, life advice, compliments, teasing Chinnu, questions about Chinnu itself, good night/morning greetings, thanks"),
  'knowledge': (90, "general knowledge and quick questions: explain something simply, math, meaning of a word, Telugu-English translation, tech questions, recipe idea, fun facts"),
  'multi': (40, "two or three commands in one sentence mixing lights, plugs, body, music, reminders"),
}

def batch(cat, desc, n):
    msg = (f"{STYLE}\nCategory: {desc}.\nWrite {n} different things Chintu says. "
           'Return JSON: {"lines": ["...", ...]}')
    r = client.chat.completions.create(model='gpt-4.1-mini', temperature=1.0, response_format={'type': 'json_object'},
                                       messages=[{'role': 'user', 'content': msg}])
    return [(cat, l.strip()) for l in json.loads(r.choices[0].message.content).get('lines', []) if l.strip()]

jobs = []
for cat, (n, desc) in CATS.items():
    n = max(2, round(n * SCALE))
    while n > 0:
        k = min(30, n); jobs.append((cat, desc, k)); n -= k

out, seen = [], set()
with cf.ThreadPoolExecutor(8) as ex:
    for res in ex.map(lambda j: batch(*j), jobs):
        for cat, l in res:
            if l.lower() not in seen: seen.add(l.lower()); out.append({'cat': cat, 'text': l})

# real things Chintu said (from Chinnu's logs), deduped
if os.path.exists('data/real_user.json'):
    real = json.load(open('data/real_user.json'))
    random.seed(1); random.shuffle(real)
    for l in real[:max(5, round(400 * SCALE))]:
        if l.lower() not in seen: seen.add(l.lower()); out.append({'cat': 'real', 'text': l})

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w') as f:
    for o in out: f.write(json.dumps(o, ensure_ascii=False) + '\n')
print(len(out), 'prompts ->', OUT)
