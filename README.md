# Chinnu — a Telugu-speaking AI companion robot dog

Chinnu is a home companion robot that talks in Telugu and English, sees, remembers, and runs the house.
The body is a SunFounder **PiDog V2** on a Raspberry Pi 5; the brain is an always-on **home server** (a second Pi 5 on NVMe).
Built and maintained by Dhileep Kumar Pagadala ([LinkedIn](https://linkedin.com/in/dhileepkumar03)).

```
   phone app · Telegram · Alexa · Meta Ray-Ban glasses · Quest 3
                       │  (Tailscale / LAN)
                       ▼
 ┌────────────────────────────────┐   HTTP + token, allow-listed   ┌──────────────────────────────┐
 │  Home server (Pi 5, NVMe)      │ ─────────────────────────────▶ │  PiDog V2 body (Pi 5)        │
 │  voice agent + tool-calling    │ ◀──── wake events, audio ───── │  controller.py (FastAPI)     │
 │  brain, memory, reminders      │ ───── heartbeat every 5 s ───▶ │  wake word (openWakeWord)    │
 │  Chinnu-LLM (Qwen2.5-3B LoRA)  │                                │  VAD mic, speaker, camera    │
 │  dashboard + touch kiosk       │                                │  gait, gyro, battery, touch  │
 │  BLE-mesh lights, plugs, cams  │                                │  watchdog: sit + stop if the │
 └───────────────┬────────────────┘                                │  server goes silent (20 s)   │
                 │ ssh tunnel                                       └──────────────────────────────┘
                 ▼
   Mac (Apple silicon): Telugu Whisper STT (MLX), YOLO-World + CLIP vision, nightly training
```

## What it does
- **Talks Telugu/English** — wake word "Chinnu" → speech-to-speech reply in a child voice, with follow-up turns.
  Realtime speech-to-speech gives ~0.5 s to first audio; the classic STT → LLM → TTS path is the fallback.
- **Acts safely** — the LLM can only call allow-listed tools (`sit`, `stand`, `walk`, `head`, `lights`, `camera`, …).
  The body runs a heartbeat watchdog: if the server stops talking for 20 s, the dog sits, stops and turns its LED red.
  A hardware watchdog reboots a hung Pi.
- **Sees and remembers** — open-vocabulary object finding (YOLO-World + CLIP for "find my keys"), face recognition
  (OpenCV YuNet + SFace), long-term memory and spoken reminders.
- **Learns overnight** — photos Chinnu collects are used to train a small YOLO11n model every night, which is shipped
  back to the server so finding works without the Mac.
- **Runs the home** — Cync bulbs over the Pi's Bluetooth mesh (cync2mqtt + local MQTT), Tuya/Govee plugs, Blink
  cameras, Alexa (fauxmo), Telegram bot, phone PWA, Nextcloud — routines like "movie mode" and "good night".

## Chinnu-LLM — its own model
`llm/` distils the cloud brain into a small local model:
1. `gen_prompts*.py` generates thousands of realistic Telugu/Tinglish requests (including mis-heard wake words).
2. `teacher.py` has the large model answer each one with the real persona and tool schema, recording full tool-call turns.
3. `lora*.yaml` fine-tunes **Qwen2.5-3B** (and a 1.5B variant) with LoRA; `score.py` / `eval_local.py` grade tool-call accuracy.
4. The fused model runs under Ollama on the home server (`chinnu:3b`) and can be switched in as the full brain.

## Speech
- Custom **"Chinnu" wake word** (openWakeWord), retrained with 30 real recordings mixed into synthetic positives:
  30/30 real clips detected at ≥ 0.93 (v1: 21/30).
- Telugu STT: **Whisper large-v2 fine-tuned for Telugu**, converted to MLX (`speech/`), benchmarked against
  large-v3 / large-v3-turbo in `bench_stt.py`; transliteration helpers for Tinglish.

## Repo layout
| Folder | Runs on | What |
|---|---|---|
| `pidog/` | PiDog | controller API, wake word, gait/gyro calibration patches |
| `server/` | home server | voice agent, brain + tools, dashboard, home integrations, systemd units |
| `llm/` | Mac → server | Chinnu-LLM data generation, distillation, LoRA training, eval, deploy |
| `speech/` | Mac | Telugu STT server, benchmarks, voice data prep |
| `vision/` | Mac | YOLO-World/CLIP server, nightly YOLO11n training |
| `glasses/` | iPhone | "Chinnu Glasses" app — Meta Ray-Ban camera + mic as Chinnu's eyes and ears |
| `hub-app/` | iPhone | Chinnu Hub app |

Secrets and home-specific data are not in the repo: copy `*.example.*` files and put API keys in `server/.env`.

## Next: Jetson Orin
Today the compute is split across two Pis, a Mac and a cloud API. The plan is to move the home server to a
**Jetson Orin** so Telugu STT, vision and Chinnu-LLM all run on one edge box — no Mac, no cloud required —
and publish benchmarks and a step-by-step guide as a reference build for multilingual home robots.
