s = open("controller.py", encoding="utf-8").read()
if "/say/stream" in s:
    print("already"); raise SystemExit
s = s.replace("VAD_TAIL = 0.8        # seconds of silence after speech -> stop",
              'VAD_TAIL = float(os.environ.get("CHINNU_VAD_TAIL", "0.5"))   # seconds of silence after speech -> stop', 1)
s = s.replace("VAD_MAX_WAIT = 3.0    # no speech at all for this long -> give up early",
              'VAD_MAX_WAIT = float(os.environ.get("CHINNU_VAD_MAX_WAIT", "2.5"))  # no speech at all for this long -> give up early', 1)
old = "# ------------------------------------------------------------------ camera (MJPEG)"
new = '''@app.post("/say/stream")
async def say_stream(request: Request, x_token: str = Header(default=""), rate: int = 24000, pitch: int = 0):
    """Play raw 16-bit mono PCM streamed in the request body while it arrives (low latency).
    pitch: cents to shift (sox, streaming) — 0 = none."""
    check(x_token)
    import asyncio
    loop = asyncio.get_running_loop()
    audio_want.set()
    got = await loop.run_in_executor(None, lambda: audio_lock.acquire(timeout=8))
    audio_want.clear()
    proc = None; sox = None
    try:
        rgb("breath", "green", 2.0)
        t0 = time.time()
        aplay = ["aplay", "-q", "-D", SPEAKER, "-t", "raw", "-r", str(rate), "-f", "S16_LE", "-c", "1", "-"]
        if pitch:
            proc = subprocess.Popen(aplay, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sox = subprocess.Popen(["sox", "-q", "-t", "raw", "-r", str(rate), "-e", "signed", "-b", "16", "-c", "1", "-",
                                    "-t", "raw", "-r", str(rate), "-e", "signed", "-b", "16", "-c", "1", "-",
                                    "pitch", str(pitch)],
                                   stdin=subprocess.PIPE, stdout=proc.stdin, stderr=subprocess.DEVNULL)
            sink = sox.stdin
        else:
            proc = subprocess.Popen(aplay, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sink = proc.stdin
        n = 0
        async for chunk in request.stream():
            if chunk:
                n += len(chunk)
                await loop.run_in_executor(None, sink.write, chunk)
        await loop.run_in_executor(None, sink.close)
        if sox:
            await loop.run_in_executor(None, sox.wait)
            try: proc.stdin.close()
            except Exception: pass
        await loop.run_in_executor(None, proc.wait)
        return {"ok": True, "bytes": n, "seconds": round(time.time() - t0, 2)}
    finally:
        for p in (sox, proc):
            if p and p.poll() is None:
                try: p.kill()
                except Exception: pass
        rgb("breath", "yellow", 0.6)
        if got:
            audio_lock.release()

# ------------------------------------------------------------------ camera (MJPEG)'''
assert old in s; s = s.replace(old, new, 1)
open("controller.py", "w", encoding="utf-8").write(s); print("patched")
