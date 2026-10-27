import sys, time, subprocess, voice
text = sys.argv[1] if len(sys.argv) > 1 else "Chinnu, stand light off cheyyi. Inka ivala weather ela undi?"
voice.tts(text, "/tmp/rt_test.wav")
subprocess.run(["sox", "/tmp/rt_test.wav", "-r", "16000", "-c", "1", "/tmp/rt_test16.wav"])
wav = open("/tmp/rt_test16.wav", "rb").read()
import realtime
t = time.time()
u, r = realtime.turn(wav, lambda s: print("USER:", s, flush=True), lambda s: print("REPLY:", s, flush=True))
print("total", round(time.time() - t, 1))
