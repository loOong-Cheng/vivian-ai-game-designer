# Voice bridge: talk to the MetaHuman

`avatar_chat.py` is the MVP conversation loop. You speak into the headset mic, and the MetaHuman answers out loud with lip-sync and a matching mood.

```
Jabra mic ─► Gradium STT (wss, semantic VAD) ─► Gemini ─► Gradium TTS (wss, 48 kHz PCM)
                                                                 │
                     ┌───────────────────────────────────────────┤
                     ▼                                           ▼
     CABLE Input (WASAPI) ═► CABLE Output ─► Live Link     Jabra earphones,
     "MetaHuman (Audio)" subject MH_Audio ─► face           delayed ~330 ms so voice
                                                            and lips line up
Gemini's mood tag ([happy], [sad] …) ─► ue_exec.py ─► SetMood on the Live Link subject
```

## Run

Prerequisites: the Unreal side from `unreal-integration/` (editor open on `L_AudioTest`, Live Link subject `MH_Audio` on CABLE Output) and `GRADIUM_API_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL` in `dt\.env`.

```powershell
cd dt
py -3 -m venv bridge\.venv
bridge\.venv\Scripts\pip install -r bridge\requirements.txt
bridge\.venv\Scripts\python bridge\avatar_chat.py
```

### Local or remote (switch with one argument)

```powershell
powershell -ExecutionPolicy Bypass -File bridge\chat.ps1                    # LOCAL: Jabra mic + Jabra earphones on this PC
powershell -ExecutionPolicy Bypass -File bridge\chat.ps1 -Remote <MAC_IP>   # REMOTE: talk from the Mac over the VPN
```

In remote mode, run this on the Mac (`unreal-integration/scripts`):

```bash
.venv/bin/python scripts/audio_send.py --host <PC_IP>                               # Mac mic -> PC UDP 50555
.venv/bin/python scripts/audio_recv.py --port 50556 --device "<Mac speakers/headphones>"  # Vivian's voice back
```

The bridge itself receives UDP 50555, so **don't run `audio_recv.py` on the PC** in this mode (it would also lip-sync your own voice). Allow Python through the Windows Firewall (Private) for UDP 50555, and through the macOS firewall for 50556. Watch Vivian through remote desktop. If her voice and lips are out of step through the VPN, adjust `--monitor-delay` (e.g. `chat.ps1 -Remote <ip> --monitor-delay 0.3`). Loopback test on the PC [measured]: transcript exact, voice returned as 3,526 packets with 0 lost.

| Flag | Use |
|---|---|
| `--model gemini-flash-lite-latest --thinking minimal` | **Recommended for the demo.** End of speech → reply text in about 1.3 s instead of 3.3 s |
| `--remote <MAC_IP>` | Mic from the Mac's `audio_send.py` (UDP `--mic-port` 50555), voice back to the Mac (`--return-port` 50556) |
| `--text` | Type your turns instead of speaking |
| `--mic-file bridge\test_audio\ask_hackathon.wav` | One automated turn with a WAV as the mic, then exit |
| `--voice <id>` | Gradium voice. Default Emma (`YTpq7expH9539ERJ`, matches Vivian); Kent is `LFZvm12tW_z0xfGo`, Sydney `jtEKaLYNn6iif5PR` |
| `--mic`, `--monitor`, `--cable` | Device name substrings. `--monitor ""` turns off the headset copy |
| `--mic-gain 2` | The Jabra is quiet (speech peaked at 0.17) |
| `--vad-threshold`, `--vad-steps` | End-of-turn sensitivity (defaults 0.5 and 3 × 80 ms) |
| `--no-moods` | Don't change the Live Link mood |
| `--body-moods` | Also switch the body loop per mood (off by default) |
| `--camera`, `--gaze-pitch-fix` | What she looks at now and then, and the eye-height correction |

## How it behaves

- **Streaming (default):** Gemini's reply is streamed and sent to TTS chunk by chunk (whole sentences; the first chunk may end at a comma), and the LLM request starts in parallel with opening the TTS socket. Measured from the end of your speech to her voice in your ear: **2.62 s → about 2.25 s** (`--no-stream` restores the old path). Faster turn-ending (VAD 2 s ×1, 3 s ×1, 3 s ×2) cut a long question off at a comma pause, so turn-ending stays at 3 s ×3. A 1.2 s mid-sentence pause still ends the turn with any setting.
- **Timing log:** each turn logs ms from the end of your speech (mic level) for: turn end, transcript, first LLM text, first chunk to TTS, first audio, playback, in your ear.
- **Turn-taking:** one long-lived STT stream. When the longest VAD horizon says inactivity > 0.5 for 3 steps, the bridge sends `flush`, and on `flushed` the words become your turn.
- **Face tuning at startup** (through the editor's PyJobs runner): lookahead 240 ms and a neutral-frame capture during silence, then a calm "listening" mood (Happiness 0.5). Each reply plays with its own mood at intensity 1.0 and then returns to the listening mood. Measured: lip closures 0.47 → 0.89, a closed mouth at rest, a smile of 0.49 when excited. Idle blinking comes from `ABP_Face_Blink` on the Unreal side.
- **Body language:** the body always plays the calm standing idle. Moods change only her face; `--body-moods` turns the per-mood body loops back on, but their posture differs 19–26° at the neck, so each reply leans in and swings back. While she talks, gentle nods and turns follow the lip-sync jaw curve. Every 4–9 s she turns to look at the camera (`--camera`, default `CAM_Face`) for 1.5–3.5 s; the bridge sends the camera position, aimed 3.8° low (`--gaze-pitch-fix`) so her eyes meet it.
- **Sync:** reply audio is buffered 0.2 s, then plays on the cable and, 0.5 s later, in your headset (audio → lips measured ~505 ms at lookahead 240). Gaps are logged as underruns.
- **Log:** every session is written to `bridge/logs/session_*.log` (transcripts, moods and whether they applied, timings, underruns, crashes).
- **Half-duplex:** from the end of your turn until the avatar has finished (+0.4 s), the mic is replaced by silence. You can't interrupt it yet.
- **Latency per turn** [measured, 2026-10-10]: Gemini 2.9 s (`gemini-flash-latest` = gemini-3.8-flash, which always thinks) or 1.0 s (flash-lite); +~0.3 s VAD flush; TTS first audio +95 ms because the socket is opened while Gemini works; +255–340 ms audio → mouth (varies per editor session; re-measure with `unreal-integration/scripts/lipsync_latency.py` and pass `--monitor-delay`).
- **Moods:** the system prompt makes Gemini start each reply with a tag. The bridge strips the tag and sets the mood (intensity 0.8) through the editor's PyJobs runner. Measured effect: Happiness raised the smile curve from 0.01 to 0.35.

## Gradium protocol notes (verified)

- STT `wss://api.gradium.ai/api/speech/asr`, header `x-api-key`. Setup `input_format: "pcm_48000"` works (the server reports model rate 24 kHz). Send 80 ms chunks as base64 `audio` messages. `step.vad` has 4 horizons (0.5, 1, 2, 3 s).
- TTS `wss://api.gradium.ai/api/speech/tts`. `output_format: "pcm"` = 48 kHz mono int16, which matches the cable. One socket per reply, since it closes on end of stream.
