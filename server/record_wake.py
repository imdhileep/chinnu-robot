"""Record real "Chinnu" samples through the robot mic: chime -> you say "Chinnu" -> saved. N reps."""
import sys, os, time, requests, voice
URL, HDR = voice.URL, voice.HDR
N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
OUT = os.path.expanduser("~/wake_samples"); os.makedirs(OUT, exist_ok=True)
ack = "/tmp/chinnu_ack.wav"
got = len([f for f in os.listdir(OUT) if f.endswith(".wav")])
print(f"existing {got}; recording {N} more. Say Chinnu after each chime.", flush=True)
i = 0
while i < N:
    requests.post(f"{URL}/say", headers=HDR, data=open(ack, "rb").read(), timeout=30)
    wav, rms = voice.listen(3)
    if not wav or rms < 3:
        print("  (nothing heard, again)", flush=True); continue
    got += 1; i += 1
    open(f"{OUT}/chinnu_{got:03d}.wav", "wb").write(wav)
    print(f"  {i}/{N} saved rms={rms:.1f}", flush=True)
    time.sleep(0.4)
print("done ->", OUT, flush=True)
