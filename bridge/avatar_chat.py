#!/usr/bin/env python3
"""Talk to the MetaHuman: mic -> Gradium STT -> Gemini -> Gradium TTS -> CABLE Input -> Live Link lip-sync.

  bridge\\.venv\\Scripts\\python bridge\\avatar_chat.py                      # speak into the Jabra headset
  bridge\\.venv\\Scripts\\python bridge\\avatar_chat.py --model gemini-flash-lite-latest   # ~2 s faster replies
  bridge\\.venv\\Scripts\\python bridge\\avatar_chat.py --text               # type instead of speaking
  bridge\\.venv\\Scripts\\python bridge\\avatar_chat.py --mic-file q.wav     # one turn from a WAV (testing)

Unreal side (see unreal-integration/): editor running with L_AudioTest and the Live Link
"MetaHuman (Audio)" subject MH_Audio listening on CABLE Output. At startup the bridge tunes that
subject through the editor's PyJobs runner: lookahead 240 ms (80 ms gave mostly jaw + lower-lip
motion; 240 ms nearly doubles lip closures) and a neutral-frame capture during silence (otherwise
the solver rests with the lower lip pulled down at 0.45). Reply audio goes to CABLE Input over
WASAPI and to the headset delayed by --monitor-delay so voice and lips line up (measured audio->jaw:
~505 ms at lookahead 240). Half-duplex: the mic is ignored from the end of your turn until the
avatar has finished. Each reply starts with a mood tag that is applied to the subject (SetMood).
Every session is logged to bridge/logs/. Keys come from dt/.env: GRADIUM_API_KEY, GEMINI_API_KEY, GEMINI_MODEL.
"""
import argparse
import asyncio
import base64
import collections
import json
import os
import queue
import re
import socket
import struct
import subprocess
import sys
import threading
import time
import types
import urllib.error
import urllib.request
import wave

import numpy as np
import sounddevice as sd
import websockets

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UE_EXEC = os.path.join(ROOT, "unreal-integration", "scripts", "ue_exec.py")
ASR_URL = "wss://api.gradium.ai/api/speech/asr"
TTS_URL = "wss://api.gradium.ai/api/speech/tts"
RATE = 48000
CHUNK = 3840  # 80 ms at 48 kHz, Gradium's frame size
MOODS = {"neutral": "NEUTRAL", "happy": "HAPPINESS", "sad": "SADNESS", "surprised": "SURPRISE",
         "excited": "EXCITEMENT", "playful": "PLAYFULNESS", "confused": "CONFUSION", "confident": "CONFIDENCE"}
# Body loop per reply mood in ABP_Body_IdleLiveLink (BodyMood): 0 stand idle, 1 happy, 2 sad, 3 surprise.
BODY_LOOPS = {"happy": 1, "excited": 1, "playful": 1, "confident": 1, "sad": 2, "surprised": 3}
SYSTEM = ("You are Vivian, a game designer. You were created today, at our hackathon, to help our team design a game: "
          "you brainstorm mechanics, characters, levels and art direction, ask what the player should feel, and "
          "prototype ideas with simple shapes on the table in front of you. You know you are a digital human (a "
          "MetaHuman in Unreal Engine) born a few hours ago, and you're proud of it; you are warm, curious, playful "
          "and full of ideas, and you talk out loud with whoever is in front of you. "
          "Answer in one to three short spoken sentences: no lists, no markdown, no emojis. Start every "
          "reply with exactly one mood tag from " + ", ".join(f"[{m}]" for m in MOODS) + ". Your face shows this "
          "mood, so pick the one that fits what you say and how you feel about it; show emotion freely and use "
          "[neutral] only for plain facts.")
# Table the avatar arranges objects on (unreal-integration/scripts/ue/workspace.py, lower half of the split screen).
WORKSPACE = {"on": False, "scene": []}
WORKSPACE_PROMPT = (
    " A table is shown on screen below you; you can arrange objects on it. When the visitor asks you to put, move or "
    "remove something, add one action tag per step right after your mood tag, then say briefly what you did. Tags: "
    "[[place <color> <shape> <relation> <target>]] to add a new object, [[place <object name> <relation> <target>]] to "
    "move one that is already there, [[remove <object name>]], [[clear]]. Colors: red, green, blue, yellow, white, "
    "black, orange, purple, pink, brown, grey. Shapes: cube, sphere, cylinder, cone (a ball is a sphere, a pyramid a "
    "cone). Relations: on, left of, right of, in front of, behind, next to; left and right are as the visitor sees "
    "the table. Targets and object names must be exactly as listed; if the visitor asks for an object that isn't "
    "there yet, create it. Example: [happy] [[place red sphere on box]] "
    "Done, the red ball is sitting on the box. Anything that is not a plain cube, sphere, cylinder or cone (an "
    "animal, a character, a vehicle, a tree, a house, a game prop) must be built from parts, never stood in for by a "
    "single shape and with no place tag for it: one build tag at the END of your reply, after what you say: "
    "[[build <name> <relation> <target>: <color> <shape> x y z w d h; <color> <shape> x y z w d h; ...]]. Units are "
    "cm: x to the visitor's right, y toward the visitor, z up from the table; x y z is the center of the part, w d h "
    "its size along x y z. Use 5 to 20 parts that touch, keep it within 60 by 40 by 50 cm, and make the biggest part "
    "the body. Example: [[build small dog on table: brown cube 0 0 14 26 11 11; brown cube 16 0 22 10 10 10; black "
    "sphere 22 0 21 3 3 3; brown cube 13 -5 29 3 2 6; brown cube 13 5 29 3 2 6; brown cylinder 9 -4 4 4 4 9; brown "
    "cylinder 9 4 4 4 4 9; brown cylinder -9 -4 4 4 4 9; brown cylinder -9 4 4 4 4 9; brown cylinder -15 0 20 2.5 2.5 "
    "10]]. A built object is then listed by its name and can be moved or removed like any other object. You also "
    "have one ready-made, game-ready asset, a photoscanned treasure chest: [[place treasure chest <relation> "
    "<target>]]; use it whenever someone asks for a chest or treasure, and don't build one. Never read "
    "the tags aloud. Objects on the table now: ")
_log_file = None


def log(msg):
    """Print and append to the session log with a timestamp."""
    line = f"{time.strftime('%H:%M:%S')}.{int(time.time() * 1000) % 1000:03d} {msg}"
    print(msg)
    if _log_file:
        _log_file.write(line + "\n")
        _log_file.flush()


def load_env(path):
    env = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: os.environ[k] for k in ("GRADIUM_API_KEY", "GEMINI_API_KEY", "GEMINI_MODEL") if k in os.environ})
    return env


def find_device(name, kind):
    hostapi = "WASAPI" if sys.platform == "win32" else ""
    for i, d in enumerate(sd.query_devices()):
        if (name.lower() in d["name"].lower() and d[f"max_{kind}_channels"] > 0
                and hostapi in sd.query_hostapis(d["hostapi"])["name"]):
            return i
    sys.exit(f"No {hostapi} {kind} device matching {name!r}; list them with: python -m sounddevice")


def wasapi_settings():
    return sd.WasapiSettings(auto_convert=True) if sys.platform == "win32" else None


class Fifo:
    """Mono float32 48 kHz queue: push() adds audio, pull(n) returns n samples (silence when empty).
    While expect_more is set, running dry counts as an underrun (a gap that shifts voice against lips)."""

    def __init__(self):
        self._chunks = collections.deque()
        self._lock = threading.Lock()
        self.queued = 0
        self.expect_more = False
        self.underruns = 0

    def push(self, audio):
        with self._lock:
            self._chunks.append(audio)
            self.queued += len(audio)

    def pull(self, frames):
        out = np.zeros(frames, np.float32)
        n = 0
        with self._lock:
            had_audio = bool(self._chunks)
            while n < frames and self._chunks:
                c = self._chunks[0]
                take = min(frames - n, len(c))
                out[n:n + take] = c[:take]
                n += take
                self.queued -= take
                if take == len(c):
                    self._chunks.popleft()
                else:
                    self._chunks[0] = c[take:]
            if self.expect_more and had_audio and n < frames:
                self.underruns += 1
        return out


class Player(Fifo):
    """Plays the queue on a local output device (CABLE Input for the face, the headset for your ears)."""

    def __init__(self, device):
        super().__init__()
        self._stream = sd.OutputStream(device=device, samplerate=RATE, channels=2, dtype="float32", latency="low",
                                       callback=self._callback, extra_settings=wasapi_settings())
        self._stream.start()

    def _callback(self, out, frames, _time, _status):
        out[:] = self.pull(frames)[:, None]


UDP_HDR = struct.Struct("!IH")  # uint32 seq + uint16 n_samples, then int16 LE: unreal-integration/scripts/audio_send.py
UDP_FRAME = 480  # 10 ms


class UdpPlayer(Fifo):
    """Sends the queue to a remote audio_recv.py (--remote: Vivian's voice back to the Mac), paced in real time in
    10 ms packets; silence while idle so the receiver's jitter buffer keeps playing."""

    def __init__(self, host, port):
        super().__init__()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._dest = (host, port)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        seq, t0, i = 0, time.perf_counter(), 0
        while True:
            pcm = (np.clip(self.pull(UDP_FRAME), -1, 1) * 32767).astype("<i2")
            try:
                self._sock.sendto(UDP_HDR.pack(seq & 0xFFFFFFFF, len(pcm)) + pcm.tobytes(), self._dest)
            except OSError:
                pass  # network hiccup: drop the packet, keep pacing
            seq, i = seq + 1, i + 1
            delay = t0 + i * UDP_FRAME / RATE - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            elif delay < -0.5:  # fell far behind (sleep stall): resync instead of bursting
                t0, i = time.perf_counter(), 0


def start_mic(device, gain, loop, q, state, level):
    def callback(indata, _frames, _time, _status):
        x = np.clip(indata[:, 0] * gain, -1, 1)
        if np.sqrt(np.mean(x * x)) > level:  # for timing: the last moment the user was audibly speaking
            state.last_voice = time.perf_counter()
        loop.call_soon_threadsafe(q.put_nowait, (x * 32767).astype("<i2").tobytes())

    stream = sd.InputStream(device=device, samplerate=RATE, channels=1, dtype="float32", blocksize=CHUNK,
                            callback=callback, extra_settings=wasapi_settings())
    stream.start()
    return stream


def start_udp_mic(port, gain, loop, q, state, level):
    """--remote: the Mac's mic from audio_send.py (10 ms UDP packets) regrouped into 80 ms STT chunks. Late packets
    are dropped, lost ones become silence, and silence is fed while nothing arrives so STT time keeps moving."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
    try:
        sock.bind(("0.0.0.0", port))
    except OSError as e:
        sys.exit(f"UDP port {port} is busy ({e}). Stop audio_recv.py on this PC: in --remote mode the bridge receives the mic.")
    sock.settimeout(0.1)
    state.udp_rx = 0

    def run():
        buf, next_seq = np.zeros(0, np.float32), None
        while True:
            try:
                pkt, _ = sock.recvfrom(4096)
            except socket.timeout:
                buf = np.concatenate([buf, np.zeros(RATE // 10, np.float32)])
                pkt = b""
            if len(pkt) >= UDP_HDR.size:
                seq, n = UDP_HDR.unpack_from(pkt)
                if next_seq is not None and seq < next_seq and next_seq - seq < 1000:
                    continue  # late / reordered
                if next_seq is not None and seq > next_seq:
                    buf = np.concatenate([buf, np.zeros(min(seq - next_seq, 10) * UDP_FRAME, np.float32)])
                next_seq = seq + 1
                state.udp_rx += 1
                buf = np.concatenate([buf, np.frombuffer(pkt, "<i2", count=n, offset=UDP_HDR.size) / 32768.0 * gain])
            while len(buf) >= CHUNK:
                c, buf = np.clip(buf[:CHUNK], -1, 1).astype(np.float32), buf[CHUNK:]
                if np.sqrt(np.mean(c * c)) > level:  # for timing: the last moment the user was audibly speaking
                    state.last_voice = time.perf_counter()
                loop.call_soon_threadsafe(q.put_nowait, (c * 32767).astype("<i2").tobytes())

    threading.Thread(target=run, daemon=True).start()
    return sock


async def file_mic(path, q, state):
    """Stream a 48 kHz mono 16-bit WAV in real time as if it were the mic, then silence."""
    with wave.open(path) as w:
        assert w.getframerate() == RATE and w.getnchannels() == 1 and w.getsampwidth() == 2, "need 48 kHz mono int16"
        data = w.readframes(w.getnframes())
    last = int(np.flatnonzero(np.abs(np.frombuffer(data, "<i2")) > 300)[-1])  # last audible sample
    data += bytes(CHUNK * 2 * 10)
    for i in range(0, len(data), CHUNK * 2):
        await q.put(data[i:i + CHUNK * 2].ljust(CHUNK * 2, b"\0"))
        if i // 2 <= last < i // 2 + CHUNK:
            state.last_voice = time.perf_counter() + (last - i // 2) / RATE
        await asyncio.sleep(CHUNK / RATE)
    while True:
        await q.put(bytes(CHUNK * 2))
        await asyncio.sleep(CHUNK / RATE)


async def stt_loop(args, env, mic_q, turns, state):
    """One long-lived STT stream. Gradium's semantic VAD ends the turn; a flush returns the last words fast."""
    async with websockets.connect(ASR_URL, additional_headers={"x-api-key": env["GRADIUM_API_KEY"]}, max_size=None) as ws:
        await ws.send(json.dumps({"type": "setup", "model_name": "default", "input_format": "pcm_48000",
                                  "json_config": {"language": args.language, "delay_in_frames": args.stt_delay}}))
        silence = bytes(CHUNK * 2)

        async def send():
            while True:
                chunk = await mic_q.get()
                audio = chunk if state.listening else silence
                await ws.send(json.dumps({"type": "audio", "audio": base64.b64encode(audio).decode()}))

        async def receive():
            words, high, flush_id, flushing, hz = [], 0, 0, False, None
            async for raw in ws:
                m = json.loads(raw)
                kind = m["type"]
                if kind == "error":
                    raise RuntimeError(f"STT error: {m}")
                if kind == "ready":
                    log("(listening - speak into the mic)" if state.listening else "(STT connected)")
                elif kind == "flushed":
                    text = " ".join(words).strip()
                    words, high, flushing = [], 0, False
                    if text and state.listening:
                        state.listening = False
                        state.transcript_at = time.perf_counter()
                        print()
                        await turns.put(text)
                elif not state.listening:
                    words, high = [], 0
                elif kind == "text":
                    words.append(m["text"])
                    print(f"\r  ... {' '.join(words)}", end="", flush=True)
                elif kind == "step":
                    if hz is None:  # VAD horizons are 0.5/1/2/3 s; pick the one closest to --vad-horizon
                        hz = min(range(len(m["vad"])), key=lambda k: abs(m["vad"][k]["horizon_s"] - args.vad_horizon))
                    high = high + 1 if m["vad"][hz]["inactivity_prob"] > args.vad_threshold else 0
                    if high >= args.vad_steps and words and not flushing:
                        flush_id += 1
                        flushing = True
                        state.turn_end = time.perf_counter()
                        await ws.send(json.dumps({"type": "flush", "flush_id": flush_id}))

        await asyncio.gather(send(), receive())


def system_prompt():
    if not WORKSPACE["on"]:
        return SYSTEM
    return SYSTEM + WORKSPACE_PROMPT + (", ".join(WORKSPACE["scene"]) or "nothing") + "."


def gemini(env, model, history, thinking):
    body = {"systemInstruction": {"parts": [{"text": system_prompt()}]}, "contents": history}
    if thinking:
        body["generationConfig"] = {"thinkingConfig": {"thinkingLevel": thinking}}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                 json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "X-goog-api-key": env["GEMINI_API_KEY"]})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        parts = d["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    except (urllib.error.URLError, KeyError, IndexError) as e:
        detail = e.read().decode()[:300] if isinstance(e, urllib.error.HTTPError) else repr(e)
        log(f"  Gemini failed: {detail}")
        return "[confused] Sorry, I lost my train of thought. Could you say that again?"


def gemini_stream(env, model, history, thinking, loop, q):
    """Thread: stream the reply (SSE) and put text deltas on the asyncio queue q, then None."""
    body = {"systemInstruction": {"parts": [{"text": system_prompt()}]}, "contents": history}
    if thinking:
        body["generationConfig"] = {"thinkingConfig": {"thinkingLevel": thinking}}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse",
        json.dumps(body).encode(), {"Content-Type": "application/json", "X-goog-api-key": env["GEMINI_API_KEY"]})
    sent = False
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            for line in r:
                line = line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                d = json.loads(line[5:])
                for p in d.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                    if p.get("text") and not p.get("thought"):
                        sent = True
                        loop.call_soon_threadsafe(q.put_nowait, p["text"])
    except (urllib.error.URLError, ValueError, KeyError, IndexError) as e:
        detail = e.read().decode()[:300] if isinstance(e, urllib.error.HTTPError) else repr(e)
        log(f"  Gemini failed: {detail}")
        if not sent:
            loop.call_soon_threadsafe(q.put_nowait, "[confused] Sorry, I lost my train of thought. Could you say that again?")
    finally:
        loop.call_soon_threadsafe(q.put_nowait, None)


def pop_chunks(buf, final=False, first=False):
    """Split streamed LLM text into TTS chunks (Gradium's LLM-to-TTS recipe: whole sentences, or ~80 characters
    cut at a comma/space; never single tokens). The first chunk of a reply may also end at a comma after 25+
    characters so speech starts sooner. Returns (chunks, rest)."""
    out = []
    if first and not re.search(r"[.!?]+[\"')\]]*\s", buf):
        m = re.search(r",\s", buf[25:])
        if m:
            cut = 25 + m.end()
            out.append(buf[:cut].strip())
            buf = buf[cut:]
    while True:
        m = re.search(r"[.!?]+[\"')\]]*\s", buf)
        if m:
            out.append(buf[:m.end()].strip())
            buf = buf[m.end():]
            continue
        if len(buf) > 80:
            cut = max(buf.rfind(", ", 0, 80) + 1, buf.rfind(" ", 0, 80))
            if cut > 20:
                out.append(buf[:cut].strip())
                buf = buf[cut:]
                continue
        break
    if final and buf.strip():
        out.append(buf.strip())
        buf = ""
    return [c for c in out if c], buf


def take_actions(buf):
    """Pull complete [[action]] tags out of streamed text. Returns (actions, (text for TTS, text held back because
    an action tag may still be arriving))."""
    acts = [a.strip() for a in re.findall(r"\[\[(.+?)\]\]", buf)]
    buf = re.sub(r"\s*\[\[.+?\]\]", "", buf)
    i = buf.find("[[")
    if i < 0 and buf.endswith("["):
        i = len(buf) - 1
    return acts, ((buf, "") if i < 0 else (buf[:i], buf[i:]))


_actions = queue.Queue()


def action_worker():
    """Thread: run [[...]] actions in the editor one at a time, in order (workspace.do), and track the scene."""
    while True:
        act = _actions.get()
        t0 = time.perf_counter()
        ok, out = ue(f"import workspace\nprint(workspace.do({act!r}))", timeout=10)
        line = out.splitlines()[-1] if out else ""
        if ok and " | scene: " in line:
            result, scene = line.split(" | scene: ", 1)
            WORKSPACE["scene"] = [x for x in scene.split(", ") if x]
            log(f"  action [[{act}]] -> {result} ({(time.perf_counter() - t0) * 1000:.0f} ms)")
        else:
            log(f"  action [[{act}]] FAILED: {out[-300:]}")


def setup_workspace(args):
    """Table scene + split-screen cameras. Returns False if the editor or workspace.py isn't reachable."""
    ok, out = ue("import importlib, workspace\nimportlib.reload(workspace)\nprint(', '.join(workspace.setup()))\n"
                 f"print(workspace.split_screen({args.camera!r}))", timeout=20)
    if not ok:
        log(f"warning: workspace disabled ({out[-300:]})")
        return False
    lines = out.splitlines()
    WORKSPACE["scene"] = [x for x in lines[-2].split(", ") if x]
    log(f"workspace: {', '.join(WORKSPACE['scene'])} | {lines[-1]}")
    threading.Thread(target=action_worker, daemon=True).start()
    return True


def parse_mood(reply):
    m = re.match(r"\s*\[(\w+)\]\s*", reply)
    mood = m.group(1).lower() if m else "neutral"
    text = re.sub(r"\[\w+\]", "", reply[m.end():] if m else reply).replace("*", "").strip()
    return (mood if mood in MOODS else "neutral"), text


def ue(code, timeout=10):
    """Run Python in the editor (PyJobs). Returns (ok, output)."""
    # stdin=DEVNULL: on Windows, starting a process that inherits stdin blocks while text mode's input() is reading it
    r = subprocess.run([sys.executable, UE_EXEC, "--timeout", str(timeout), "-c", code], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def subject_code(subject):
    return ("import unreal\n"
            f"k = [k for k in unreal.LiveLinkBlueprintLibrary.get_live_link_subjects(True, True) if str(k.subject_name.name) == {subject!r}]\n"
            f"if not k: raise RuntimeError('Live Link subject {subject} not found')\n"
            "s = unreal.MetaHumanLocalLiveLinkSourceBlueprint.get_subject_settings(k[0])\n")


GAZE = {"camera": "CAM_Face", "pitch_fix": 3.8}  # set from args in main()


def body_code(actor, body):
    """Python run in the editor: BodyMood + CamTarget on ABP_Body_IdleLiveLink. CamTarget is the camera, lowered by
    distance * tan(pitch_fix) because Vivian's eyes rest ~3.8 deg above the head's forward axis (measured)."""
    return ("import math\n"
            "E = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()\n"
            f"a = [x for x in E if x.get_actor_label() == {actor!r}]\n"
            f"cams = [x for x in E if x.get_actor_label() == {GAZE['camera']!r}]\n"
            "ai = a[0].get_editor_property('Body').get_anim_instance() if a else None\n"
            "try:\n"
            f"    ai.set_editor_property('BodyMood', {body})\n"
            "    if cams:\n"
            "        c = cams[0].get_actor_location(); h = a[0].get_editor_property('Face').get_socket_location('head')\n"
            f"        c.z -= (c - h).length() * math.tan(math.radians({GAZE['pitch_fix']}))\n"
            "        ai.set_editor_property('CamTarget', c)\n"
            "except Exception:\n"
            "    pass  # body AnimBP without mood loops / gaze\n")


def set_mood(subject, mood, intensity, actor="", body=0):
    """Face mood on the Live Link subject; with actor, also BodyMood and the gaze target on the body AnimBP."""
    code = subject_code(subject) + (f"s.set_mood(unreal.AudioDrivenAnimationMood.{MOODS[mood]}); "
                                    f"s.set_mood_intensity({intensity}); print(s.get_mood())\n")
    if actor:
        code += body_code(actor, body)
    ok, out = ue(code, timeout=5)
    log(f"  mood -> {mood} ({intensity}, body loop {body}): {'ok' if ok else 'FAILED ' + out[-200:]}")


def restart_live_link(args):
    """Re-apply the Live Link preset, which recreates the audio source. Its solver once stopped mid-session (jaw curve
    frozen at one value, nothing in the editor log) and only a restart of the source brought it back."""
    if not args.preset:
        return
    ok, out = ue(f"import unreal\nprint(unreal.load_asset({args.preset!r}).apply_to_client())")
    if not ok:
        log(f"warning: couldn't re-apply Live Link preset {args.preset}: {out[-200:]}")
        return
    for _ in range(25):  # the subject comes back within a second or two
        if ue(subject_code(args.subject) + "print('ok')", timeout=5)[0]:
            log(f"Live Link audio source restarted ({args.preset})")
            time.sleep(3.0)  # let the solver settle: a neutral frame taken after 1 s left the jaw at ~1/3 range
            return
        time.sleep(0.2)
    log(f"warning: subject {args.subject} didn't come back after re-applying {args.preset}")


def tune_unreal(args):
    """Lookahead + neutral-frame calibration on the audio subject. Returns False if the editor isn't reachable."""
    restart_live_link(args)
    ok, out = ue(subject_code(args.subject) + f"s.set_lookahead({args.lookahead}); "
                 "s.set_mood(unreal.AudioDrivenAnimationMood.NEUTRAL); s.set_mood_intensity(1.0); print('lookahead', s.get_lookahead())")
    if not ok:
        log(f"warning: can't tune the Live Link subject, moods disabled ({out[-300:]}). Is the editor running with "
            f"subject {args.subject}? (Live Link > + Source > MetaHuman (Audio) > CABLE Output, or restart the editor)")
        return False
    log(f"Live Link {args.subject}: {out.splitlines()[-1]}")
    if not args.calibrate:
        return True
    time.sleep(1.0)  # let a previous mood blend out before taking the resting face as neutral
    for _ in range(10):  # don't capture mid-blink: the blink curve is part of the calibration set
        ok, out = ue(subject_code(args.subject) +
                     "blink = max((a.get_editor_property('Body').get_anim_instance().get_curve_value('CTRL_expressions_eyeBlinkL') "
                     "for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() "
                     "if a.get_actor_label() == " + repr(args.actor) + "), default=0.0)\n"
                     "if blink < 0.1: s.set_editor_property('capture_neutral_frame_countdown', 5)\n"
                     "print('blink', round(blink, 2))")
        try:
            blink = float(out.split()[-1]) if ok else 1.0
        except ValueError:
            blink = 1.0
        if blink < 0.1:
            time.sleep(0.5)
            ok, out = ue(subject_code(args.subject) + "print(len(s.get_editor_property('neutral_frame')))")
            log(f"neutral frame captured during silence ({out} values)" if ok else f"neutral capture check failed: {out}")
            break
        time.sleep(0.15)
    else:
        log("warning: neutral capture skipped (eyes kept blinking)")
    if args.idle_mood:
        set_mood(args.subject, args.idle_mood, args.idle_intensity, args.actor, 0)
    return True


async def open_tts(env, voice):
    ws = await websockets.connect(TTS_URL, additional_headers={"x-api-key": env["GRADIUM_API_KEY"]}, max_size=None)
    await ws.send(json.dumps({"type": "setup", "model_name": "default", "voice_id": voice, "output_format": "pcm"}))
    return ws


async def speak(ws, chunks, cable, headset, args):
    """Send text chunks (async iterator) to TTS while streaming its audio into the cable (face) and, delayed, the
    headset (ears). Audio is held back until --prebuffer seconds are ready, so a slow first chunk can't open a gap
    on one output only. Returns timestamps: first chunk sent, first audio received, playback start."""
    ts = {"sent": None, "audio": None, "play": None}
    pending, started = [], False
    players = [p for p in (cable, headset) if p]

    def start():
        ts["play"] = time.perf_counter()
        if headset:
            headset.push(np.zeros(int(args.monitor_delay * RATE), np.float32))
        for pcm in pending:
            for p in players:
                p.push(pcm)

    async def send():
        async for chunk in chunks:
            ts["sent"] = ts["sent"] or time.perf_counter()
            await ws.send(json.dumps({"type": "text", "text": chunk + " "}))
        await ws.send(json.dumps({"type": "end_of_stream"}))

    sender = asyncio.create_task(send())
    try:
        for p in players:
            p.expect_more = True
        async for raw in ws:
            m = json.loads(raw)
            if m["type"] == "audio":
                pcm = np.frombuffer(base64.b64decode(m["audio"]), "<i2").astype(np.float32) / 32768
                ts["audio"] = ts["audio"] or time.perf_counter()
                if started:
                    for p in players:
                        p.push(pcm)
                else:
                    pending.append(pcm)
                    if sum(len(c) for c in pending) >= args.prebuffer * RATE:
                        start()
                        started = True
            elif m["type"] == "error":
                log(f"  TTS error: {m}")
                break
            elif m["type"] == "end_of_stream":
                break
        if not started:
            start()
        await sender
    finally:
        sender.cancel()
        for p in players:
            p.expect_more = False
        await ws.close()
    return ts


async def converse(args, env, turns, cable, headset, state):
    history = []
    loop = asyncio.get_running_loop()
    while True:
        user = await turns.get()
        scripted = user.startswith("[say]")
        log(f"You: {user}" if not scripted else "(greeting)")
        marks = {"speech_end": state.last_voice, "turn_end": state.turn_end, "transcript": state.transcript_at}
        state.turn_end = state.transcript_at = None
        tts = asyncio.create_task(open_tts(env, args.voice))  # connect while Gemini thinks

        def apply_mood(mood):
            if state.moods:
                threading.Thread(target=set_mood, args=(args.subject, mood, args.mood_intensity, args.actor,
                                                        BODY_LOOPS.get(mood, 0) if args.body_moods else 0),
                                 daemon=True).start()

        async def reply_chunks():
            """Yield TTS chunks. Streaming: chunks leave as soon as each sentence is complete."""
            if scripted or not args.stream:
                if scripted:
                    reply = user[5:].strip()
                else:
                    marks["llm"] = time.perf_counter()
                    reply = await asyncio.to_thread(gemini, env, args.model, history, args.thinking)
                    marks["text"] = time.perf_counter()
                    history.append({"role": "model", "parts": [{"text": reply}]})
                acts, (reply, _) = take_actions(reply)
                for a in acts:
                    _actions.put(a)
                mood, text = parse_mood(reply)
                log(f"Avatar [{mood}]: {text}")
                apply_mood(mood)
                yield text
                return
            buf, full, mood, first = "", "", None, True
            while (delta := await q.get()) is not None:
                marks.setdefault("text", time.perf_counter())
                full += delta
                buf += delta
                if mood is None:
                    head = buf.lstrip()
                    if head.startswith("[") and "]" not in head and len(head) < 24:
                        continue  # wait for the whole [mood] tag
                    m = re.match(r"\s*\[(\w+)\]\s*", buf)
                    mood = m.group(1).lower() if m and m.group(1).lower() in MOODS else "neutral"
                    buf = buf[m.end():] if m else buf
                    apply_mood(mood)
                acts, (ready, held) = take_actions(buf)
                for a in acts:  # runs in the editor while she talks
                    marks.setdefault("action", time.perf_counter())
                    _actions.put(a)
                chunks, buf = pop_chunks(ready, first=first)
                buf += held
                first = first and not chunks
                for c in chunks:
                    yield re.sub(r"\[\w+\]", "", c).replace("*", "").strip()
            for a in take_actions(buf + "]]" if "[[" in buf else buf)[0]:  # unterminated tag at the very end
                _actions.put(a)
            buf = re.sub(r"\[\[.*", "", re.sub(r"\s*\[\[.+?\]\]", "", buf))
            for c in pop_chunks(buf, final=True)[0]:
                yield re.sub(r"\[\w+\]", "", c).replace("*", "").strip()
            marks["text_done"] = time.perf_counter()
            history.append({"role": "model", "parts": [{"text": full}]})
            log(f"Avatar [{mood}]: {re.sub(r'^\s*\[\w+\]\s*', '', full).strip()}")  # action tags shown as sent

        if not scripted:
            history.append({"role": "user", "parts": [{"text": user}]})
            if args.stream:  # start the LLM now, in parallel with opening the TTS socket
                q = asyncio.Queue()
                marks["llm"] = time.perf_counter()
                threading.Thread(target=gemini_stream, args=(env, args.model, history, args.thinking, loop, q),
                                 daemon=True).start()
        under0 = (cable.underruns, headset.underruns if headset else 0)
        ts = await speak(await tts, reply_chunks(), cable, headset, args)
        if not scripted:
            ref = marks["speech_end"] or marks["turn_end"]
            ms = lambda t: f"+{(t - ref) * 1000:.0f}" if t and ref else "?"
            log(f"  timing ms from {'end of your speech' if marks['speech_end'] else 'turn end'}: "
                f"turn end {ms(marks['turn_end'])} | transcript {ms(marks['transcript'])} | "
                f"first LLM text {ms(marks.get('text'))} (LLM first token {(marks['text'] - marks['llm']) * 1000:.0f}) | "
                f"first chunk to TTS {ms(ts['sent'])} | first audio {ms(ts['audio'])} | playback {ms(ts['play'])} | "
                f"in your ear {ms(ts['play'] + args.monitor_delay) if ts['play'] else '?'} "
                f"[{'stream' if args.stream else 'no-stream'}, VAD h{args.vad_horizon:g}x{args.vad_steps}]")
        while cable.queued > 0 or (headset and headset.queued > 0):
            await asyncio.sleep(0.05)
        gaps = (cable.underruns - under0[0], (headset.underruns - under0[1]) if headset else 0)
        if any(gaps):
            log(f"  WARNING audio underruns during reply: cable {gaps[0]}, headset {gaps[1]} (voice/lips may drift)")
        if state.moods and args.idle_mood:  # the reply mood persists at rest; switch to a calm listening face
            await asyncio.sleep(0.6)  # solver lag: let the last syllables finish under the reply mood
            threading.Thread(target=set_mood, args=(args.subject, args.idle_mood, args.idle_intensity, args.actor, 0),
                             daemon=True).start()
        await asyncio.sleep(args.tail)
        if args.mic_file and not scripted:
            return
        state.listening = True
        log("(listening)")


async def text_input(turns, state):
    while True:
        try:
            line = (await asyncio.to_thread(input, "> ")).strip()
        except EOFError:  # piped input ended: finish the last reply, then exit
            while not (state.listening and turns.empty()):
                await asyncio.sleep(0.2)
            return
        if line:
            state.listening = False
            await turns.put(line)


async def run(args, env):
    loop = asyncio.get_running_loop()
    moods = args.moods and await asyncio.to_thread(tune_unreal, args)
    WORKSPACE["on"] = args.workspace and await asyncio.to_thread(setup_workspace, args)
    state = types.SimpleNamespace(listening=False, turn_end=None, transcript_at=None, last_voice=None, moods=moods)
    cable = Player(find_device(args.cable, "output"))
    if args.remote:  # Vivian's voice back to the Mac (audio_recv.py --port RETURN_PORT there)
        headset = UdpPlayer(args.remote, args.return_port)
    else:
        headset = Player(find_device(args.monitor, "output")) if args.monitor else None
    turns, mic_q = asyncio.Queue(), asyncio.Queue()
    where = (f"REMOTE: mic <- UDP :{args.mic_port}, voice -> {args.remote}:{args.return_port}" if args.remote
             else f"LOCAL: mic {args.mic}, headset {args.monitor or 'off'}")
    log(f"{where} | model {args.model} | voice {args.voice} | face audio -> {args.cable} "
        f"(+{args.monitor_delay * 1000:.0f} ms) | lookahead {args.lookahead} ms")
    if args.greeting and not args.mic_file:
        await turns.put("[say]" + args.greeting)
    tasks = [asyncio.create_task(converse(args, env, turns, cable, headset, state))]
    if args.text:
        tasks.append(asyncio.create_task(text_input(turns, state)))
    else:
        if args.mic_file:
            tasks.append(asyncio.create_task(file_mic(args.mic_file, mic_q, state)))
        else:
            if args.remote:
                state.mic = start_udp_mic(args.mic_port, args.mic_gain, loop, mic_q, state, args.mic_level)
            else:
                state.mic = start_mic(find_device(args.mic, "input"), args.mic_gain, loop, mic_q, state, args.mic_level)
        tasks.append(asyncio.create_task(stt_loop(args, env, mic_q, turns, state)))
    if not args.greeting or args.mic_file:
        state.listening = True
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    for t in done:
        t.result()


def main():
    global _log_file
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    env = load_env(os.path.join(ROOT, ".env"))
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default=env.get("GEMINI_MODEL", "gemini-flash-latest"))
    p.add_argument("--thinking", default="", help='Gemini thinkingLevel, e.g. "minimal" (flash-lite) or "low"')
    p.add_argument("--voice", default="YTpq7expH9539ERJ", help="Gradium voice_id (default Emma, US English; Kent = LFZvm12tW_z0xfGo)")
    p.add_argument("--language", default="en")
    p.add_argument("--mic", default="Jabra", help="input device name substring (WASAPI on Windows)")
    p.add_argument("--remote", metavar="MAC_IP", help="talk from the Mac: mic from its audio_send.py (UDP --mic-port), "
                                                     "voice back to MAC_IP:--return-port for its audio_recv.py")
    p.add_argument("--mic-port", type=int, default=50555, help="UDP port audio_send.py sends the Mac mic to")
    p.add_argument("--return-port", type=int, default=50556, help="UDP port of audio_recv.py on the Mac")
    p.add_argument("--mic-gain", type=float, default=1.0)
    p.add_argument("--mic-file", help="use a 48 kHz mono WAV as the mic for one turn, then exit")
    p.add_argument("--text", action="store_true", help="type your turns instead of speaking")
    p.add_argument("--cable", default="CABLE Input", help="output feeding Unreal's Live Link audio source")
    p.add_argument("--monitor", default="Jabra", help='output you listen on ("" to disable)')
    p.add_argument("--monitor-delay", type=float, default=0.65,
                   help="headset delay so voice matches the lips (measured ~505 ms at lookahead 240 with one viewport, "
                        "~645 ms with the split screen; ~335 ms at lookahead 80; "
                        "re-measure with unreal-integration/scripts/lipsync_latency.py)")
    p.add_argument("--prebuffer", type=float, default=0.2, help="seconds of TTS audio buffered before playback starts")
    p.add_argument("--lookahead", type=int, default=240, help="audio solver lookahead, 80-240 ms (higher = better lips, more lag)")
    p.add_argument("--no-calibrate", dest="calibrate", action="store_false", help="skip the neutral-frame capture")
    p.add_argument("--stt-delay", type=int, default=8, help="Gradium delay_in_frames (80 ms frames)")
    p.add_argument("--vad-threshold", type=float, default=0.5)
    p.add_argument("--vad-horizon", type=float, default=3.0,
                   help="Gradium VAD horizon (0.5/1/2/3 s) whose inactivity probability ends the turn. Faster settings "
                        "(2 s x1, 3 s x1, 3 s x2) cut a long question off at a comma pause in our tests")
    p.add_argument("--vad-steps", type=int, default=3, help="consecutive 80 ms steps above threshold to end a turn")
    p.add_argument("--no-stream", dest="stream", action="store_false",
                   help="wait for the whole Gemini reply before TTS (default: stream sentence by sentence)")
    p.add_argument("--mic-level", type=float, default=0.004, help="mic RMS counted as speech, for the timing log only")
    p.add_argument("--tail", type=float, default=0.4, help="seconds after the reply before listening again")
    p.add_argument("--subject", default="MH_Audio")
    p.add_argument("--restart-audio", dest="preset", nargs="?", const="/Game/LiveLink/LLP_MH_Audio", default="",
                   help="re-apply this Live Link preset at startup to restart a frozen audio source (jaw stuck). Off by "
                        "default: the restarted source lip-synced worse (~0.65 s lag, weaker mouth) than after an "
                        "editor restart, which is the better fix")
    p.add_argument("--camera", default="CAM_Face", help="actor the avatar looks at now and then")
    p.add_argument("--gaze-pitch-fix", type=float, default=3.8, help="degrees to aim the head below the camera so the eyes meet it")
    p.add_argument("--actor", default="MH_Avatar", help="level actor label of the MetaHuman")
    p.add_argument("--no-moods", dest="moods", action="store_false")
    p.add_argument("--mood-intensity", type=float, default=1.0)
    p.add_argument("--idle-mood", default="happy", choices=[""] + list(MOODS), help="face while listening")
    p.add_argument("--idle-intensity", type=float, default=0.5)
    p.add_argument("--body-moods", action="store_true",
                   help="also switch the body loop per mood. Off by default: the emotion loops' posture differs "
                        "19-26 deg at the neck from the idle, so every reply leaned in and swung back")
    p.add_argument("--no-workspace", dest="workspace", action="store_false",
                   help="no table / [[place ...]] actions (needs the two-pane viewport layout, see workspace.py)")
    p.add_argument("--greeting", default="[happy] Hi, I'm Vivian, your game designer for today's hackathon. What shall we make?")
    args = p.parse_args()
    GAZE.update(camera=args.camera, pitch_fix=args.gaze_pitch_fix)
    for k in ("GRADIUM_API_KEY", "GEMINI_API_KEY"):
        if not env.get(k):
            sys.exit(f"{k} missing: put it in {os.path.join(ROOT, '.env')}")
    os.makedirs(os.path.join(ROOT, "bridge", "logs"), exist_ok=True)
    path = os.path.join(ROOT, "bridge", "logs", time.strftime("session_%Y%m%d_%H%M%S.log"))
    _log_file = open(path, "w", encoding="utf-8")
    log(f"log: {path}")
    try:
        asyncio.run(run(args, env))
    except KeyboardInterrupt:
        log("bye")
    except Exception:
        import traceback
        log("CRASH\n" + traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
