# Audio Live Link setup

Pipeline:

```
[mic] ─────────────────────────────────────────────┐
                                                   ▼
[WAV / Python bridge] ─► BlackHole 2ch (output) ═► BlackHole 2ch (input) ─► Live Link "MetaHuman (Audio)" source ─► subject ─► MetaHuman face
```

BlackHole is a CoreAudio loopback driver: whatever is played *to* its output device shows up on its input device.

## 1. Install BlackHole (one-time, needs your password)

```bash
brew install --cask blackhole-2ch
```

The cask runs a `.pkg` installer, which asks for your macOS password. If the device doesn't appear afterwards, run `sudo killall coreaudiod` or reboot.

Verify:

```bash
cd unreal-integration && .venv/bin/python scripts/play_to_device.py --list | grep -i blackhole
```

To **hear** the audio while it also goes to Unreal (optional), open **Audio MIDI Setup → + → Create Multi-Output Device** and tick *BlackHole 2ch* and *MacBook Air speakers*. BlackHole must be the clock source, with drift correction on the speakers. The bridge then plays to the Multi-Output device, and Unreal still listens on *BlackHole 2ch* (input).

## 2. macOS microphone permission

The first time Unreal Editor opens an audio input, macOS asks for microphone access. If you dismissed it, go to **System Settings → Privacy & Security → Microphone** and enable *UnrealEditor*. This applies to BlackHole too, because it's an input device.

## 3. Create the source in Unreal (documented editor steps)

From [Using a MetaHuman Audio Source](https://dev.epicgames.com/documentation/metahuman/using-a-metahuman-audio-source-in-unreal-engine):

1. **Window → Virtual Production → Live Link**.
2. **+ Source → MetaHuman (Audio)**.
3. Select the new source. Under **Create**, set **Audio Device** to `MacBook Air麦克风` (mic test) or `BlackHole 2ch` (WAV or bridge test).
4. Set **Subject Name**: `MH_Audio_Mic` or `MH_Audio_BH`.
5. Click **Connect**. A green tick beside the subject means it's running.
6. Select the subject and check the **Monitor** volume meter while audio plays. The meter only shows that input is live; it isn't a calibrated level meter.

Binding to the MetaHuman is covered in `metahuman_setup.md`.

## 4. Interface contract for the Python audio bridge (teammate)

| Property | Value |
|---|---|
| Output device | `BlackHole 2ch` (or a Multi-Output device that includes it) |
| Sample rate | **48 000 Hz** (BlackHole default; avoids CoreAudio resampling) |
| Format | float32 or int16 PCM; the bridge writes to CoreAudio and the format is negotiated there |
| Channels | 2 (BlackHole 2ch). For mono speech, duplicate it to L and R. |
| Level | Normal speech level, peaks around −3 dBFS, no clipping |
| Silence | Send real silence (zeros) between utterances rather than closing the stream. Unreal keeps the device open regardless. |
| Reference impl | `scripts/play_to_device.py` (uses `sounddevice`) |

**On Windows** [measured 2026-10-10]: the output device is **"CABLE Input (VB-Audio Virtual Cable)" opened through WASAPI** (shared mode, 48 kHz). Unreal listens on "CABLE Output", where the only format offered is IEEE Float 2 ch @ 48000 Hz. Writing through MME instead (sounddevice's first name match) made audio → jaw 465 ms instead of 270 ms. The implementation is `dt/bridge/avatar_chat.py`, which also sends a copy to the headset delayed by 270 ms so voice and lips line up.

The bridge doesn't talk to Unreal directly for audio. The only coupling is the audio device. Emotion events (Phase 4) will go through a separate channel; see `mood_test.md`.

## 5. Test commands

```bash
cd unreal-integration
./scripts/make_test_wavs.sh                       # creates test_audio/clip{1,2,3}.wav (48 kHz mono)
.venv/bin/python scripts/play_to_device.py --device "BlackHole 2ch" test_audio/clip1.wav test_audio/clip2.wav test_audio/clip3.wav --gap 1.5
```
