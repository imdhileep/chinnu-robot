"""Teach Chinnu Chintu's voice: Chinnu asks, you talk ~6 s each time, near the robot.
Usage: venv/bin/python enroll_voice.py [rounds=8] [name=Chintu]
Stop chinnu-voice first (it uses the mic)."""
import sys, time
import voice, speaker

rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 8
name = sys.argv[2] if len(sys.argv) > 2 else 'Chintu'
prompts = ["Mellaga, nidra voice lo matladu.", 'Nee peru, nee pani gurinchi cheppu.', 'Ee roju em chesavo cheppu.', 'Nee favourite cinema gurinchi cheppu.',
           'Okka paata konchem paadu.', 'Mana intlo vunna vastuvula gurinchi cheppu.', 'Rendu nimishala katha cheppu.',
           'Gattiga, konchem dooram nunchi matladu.', 'Mellaga, daggara nunchi matladu.', 'Chinnu ki edaina order ivvu.',
           'Nee friends gurinchi cheppu.']
voice.say('Anna, nee voice nerchukuntunna. Nenu adiginappudu aaru seconds matladu.')
time.sleep(1)
for i in range(rounds):
    voice.say(prompts[i % len(prompts)])
    wav, rms = voice.listen(7)
    if not wav:
        print(i, 'no speech'); voice.say('Vinapadaledu, malli.'); continue
    r = speaker.enroll(name, wav); print(i, 'rms', round(rms, 1), r, flush=True)
voice.say('Ayipoyindi anna! Ippudu nee voice gurthupadatha.')
