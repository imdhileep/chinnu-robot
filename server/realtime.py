"""OpenAI Realtime (speech-to-speech) turn for Chinnu.
One persistent WebSocket session (reconnects as needed). turn(wav_bytes) -> sends the user's clip,
streams the spoken reply straight to the robot's /say/stream, runs tools, returns (user_text, reply_text).
Falls back (raises) so the caller can use the classic STT->GPT->TTS pipeline."""
import base64, json, os, threading, time, queue
import numpy as np
import requests
from websockets.sync.client import connect
import brain, voice, extras, owner
_mode = 'owner'          # mode of the current websocket session

URL = 'wss://api.openai.com/v1/realtime'
MODEL = voice.V.get('realtime_model', 'gpt-realtime')
VOICE = voice.V.get('realtime_voice', 'marin')
PITCH = int(voice.V.get('child_pitch', 600)) if voice.V.get('child_voice', True) else 0
API_KEY = os.environ.get('OPENAI_API_KEY', '')
_lock = threading.Lock()
_ws = None
_ws_at = 0.0
_debug = bool(voice.V.get('realtime_debug', False))

def _tools():
    allowed = None if _mode == 'owner' else owner.GUEST_TOOLS
    return [{'type': 'function', 'name': t['function']['name'], 'description': t['function'].get('description', ''),
             'parameters': t['function'].get('parameters', {'type': 'object', 'properties': {}})} for t in brain.TOOLS if allowed is None or t['function']['name'] in allowed]

def _instructions():
    if _mode != 'owner':
        return owner.GUEST_PROMPT
    return (brain.SYSTEM + extras.memory_block() +
            '\nVOICE MODE: you are speaking out loud. Keep replies short (1-2 sentences) unless asked for more. '
            'Always answer in natural spoken Telugu (Telugu words, you may mix common English tech words). '
            'Never read out JSON or tool output verbatim - summarise it in Telugu. '
            'TOOLS ARE MANDATORY: for weather, time/date, news, lights, plugs, robot body actions, camera, faces, reminders, '
            'memory and file search you MUST call the matching tool and answer only from its result - never guess or invent such information. '
            'Do not announce that you are calling a tool; just call it, then answer. '
            'You are in OWNER mode: the speaker was verified as Chintu (face or phone unlock).')

def _session_update(ws):
    ws.send(json.dumps({'type': 'session.update', 'session': {
        'type': 'realtime', 'model': MODEL, 'instructions': _instructions(),
        'output_modalities': ['audio'],
        'audio': {'input': {'format': {'type': 'audio/pcm', 'rate': 24000},
                            'transcription': {'model': 'gpt-4o-mini-transcribe', 'language': 'te'},
                            'turn_detection': None},
                  'output': {'format': {'type': 'audio/pcm', 'rate': 24000}, 'voice': VOICE}},
        'tools': _tools(), 'tool_choice': 'auto', 'max_output_tokens': 400}}))

def _connect():
    global _ws, _ws_at
    ws = connect(f'{URL}?model={MODEL}', additional_headers={'Authorization': f'Bearer {API_KEY}'},
                 open_timeout=8, close_timeout=2, max_size=16 * 1024 * 1024)
    # wait for session.created, then configure
    t0 = time.time()
    while time.time() - t0 < 8:
        ev = json.loads(ws.recv(timeout=8))
        if ev.get('type') == 'session.created': break
    _session_update(ws)
    _ws, _ws_at = ws, time.time()
    print('[realtime] connected', flush=True)
    return ws

def _get_ws():
    global _ws
    if _ws is None or time.time() - _ws_at > 50 * 60:
        if _ws is not None:
            try: _ws.close()
            except Exception: pass
            _ws = None
        return _connect()
    return _ws

def warmup():
    try:
        with _lock: _get_ws()
    except Exception as e: print('[realtime] warmup failed', e, flush=True)

def _wav_to_pcm24k(wav_bytes):
    import io, wave
    with wave.open(io.BytesIO(wav_bytes)) as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32)
    if ch > 1: x = x.reshape(-1, ch).mean(axis=1)
    peak = np.abs(x).max() or 1.0
    if peak < 8000: x = x * (8000.0 / peak)          # quiet HAT mic -> normal level
    if sr != 24000:
        idx = np.arange(0, len(x), sr / 24000.0)
        x = np.interp(idx, np.arange(len(x)), x)
    return np.clip(x, -32768, 32767).astype(np.int16).tobytes()

def _play_stream(chunks_q):
    """POST a generator of PCM chunks to the robot (blocks until playback done)."""
    def gen():
        while True:
            c = chunks_q.get()
            if c is None: return
            yield c
    try:
        requests.post(f'{voice.URL}/say/stream', headers={**voice.HDR, 'Content-Type': 'application/octet-stream'},
                      params={'rate': 24000, 'pitch': PITCH}, data=gen(), timeout=120)
    except Exception as e:
        print('[realtime] play error', e, flush=True)

def turn(wav_bytes, on_user=None, on_reply=None):
    """Run one spoken exchange. Returns (user_transcript, reply_transcript). Retries once on a dropped socket."""
    global _ws
    try:
        return _turn(wav_bytes, on_user, on_reply)
    except Exception as e:
        print('[realtime] turn error, reconnecting:', str(e)[:120], flush=True)
        try: _ws.close()
        except Exception: pass
        _ws = None
        return _turn(wav_bytes, on_user, on_reply)

def set_mode(mode):
    """Switch owner/guest. A switch always starts a FRESH session so no earlier conversation leaks."""
    global _mode, _ws
    if mode == _mode: return
    with _lock:
        _mode = mode
        if _ws is not None:
            try: _ws.close()
            except Exception: pass
            _ws = None
    print(f'[realtime] mode -> {mode} (new session)', flush=True)

def _turn(wav_bytes, on_user=None, on_reply=None):
    with _lock:
        ws = _get_ws()
        pcm = _wav_to_pcm24k(wav_bytes)
        t0 = time.time()
        for i in range(0, len(pcm), 32000):
            ws.send(json.dumps({'type': 'input_audio_buffer.append', 'audio': base64.b64encode(pcm[i:i + 32000]).decode()}))
        ws.send(json.dumps({'type': 'input_audio_buffer.commit'}))
        ws.send(json.dumps({'type': 'response.create'}))
        user_text, reply_text = '', ''
        q = None; player = None; first_audio = None
        pending_calls = {}
        while True:
            ev = json.loads(ws.recv(timeout=60))
            t = ev.get('type', '')
            if _debug and 'delta' not in t: print('[realtime]', t, flush=True)
            if t in ('response.output_audio.delta', 'response.audio.delta'):
                if q is None:
                    q = queue.Queue(); player = threading.Thread(target=_play_stream, args=(q,), daemon=True); player.start()
                    first_audio = time.time() - t0; print(f'[realtime] first audio {first_audio:.2f}s', flush=True)
                q.put(base64.b64decode(ev['delta']))
            elif t in ('response.output_audio_transcript.delta', 'response.audio_transcript.delta'):
                reply_text += ev.get('delta', '')
            elif t == 'conversation.item.input_audio_transcription.completed':
                user_text = (ev.get('transcript') or '').strip()
                if on_user: on_user(user_text)
            elif t == 'response.function_call_arguments.done':
                pending_calls[ev['call_id']] = (ev['name'], ev.get('arguments') or '{}')
            elif t == 'response.done':
                try:
                    u = (ev.get('response') or {}).get('usage') or {}
                    ind, outd = u.get('input_token_details') or {}, u.get('output_token_details') or {}
                    import usage
                    usage.record('realtime', MODEL, text_in=ind.get('text_tokens', 0) - (ind.get('cached_tokens', 0) or 0),
                                 cached_in=ind.get('cached_tokens', 0) or 0, audio_in=ind.get('audio_tokens', 0),
                                 text_out=outd.get('text_tokens', 0), audio_out=outd.get('audio_tokens', 0))
                except Exception as _e: print('[usage]', _e, flush=True)
                if pending_calls:
                    for call_id, (name, args) in pending_calls.items():
                        try: a = json.loads(args)
                        except Exception: a = {}
                        if _mode != 'owner' and not owner.guest_allowed(name, a):
                            result = {'ok': False, 'error': 'not allowed for guests'}
                        else:
                            result = brain.run_tool(name, a)
                        print(f'  [tool] {name}({a}) -> {str(result)[:160]}', flush=True)
                        ws.send(json.dumps({'type': 'conversation.item.create', 'item': {
                            'type': 'function_call_output', 'call_id': call_id, 'output': json.dumps(result)[:4000]}}))
                    pending_calls = {}
                    ws.send(json.dumps({'type': 'response.create'}))
                    continue
                break
            elif t == 'error':
                print('[realtime] error', ev.get('error'), flush=True)
                if q is None: raise RuntimeError(str(ev.get('error')))
                break
        if q is not None:
            q.put(None); player.join(timeout=120)
        reply_text = reply_text.strip()
        if on_reply and reply_text: on_reply(reply_text)
        # keep the text brain's history in sync (daily summary, follow-ups via text chat)
        try:
            if _mode == 'owner' and user_text: brain.history.append({'role': 'user', 'content': user_text})
            if _mode == 'owner' and reply_text: brain.history.append({'role': 'assistant', 'content': reply_text})
        except Exception: pass
        print(f'[realtime] turn done in {time.time() - t0:.1f}s', flush=True)
        return user_text, reply_text
