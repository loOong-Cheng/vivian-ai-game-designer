# Test results

Each value is tagged **[measured]** or **[estimate]**.

## Environment [measured]

See `macos_compatibility.md`: MacBook Air M5, 16 GB, macOS 26.5.1, Xcode 26.6.

## Log

| Time (2026-10-10) | Step | Result |
|---|---|---|
| 11:25 | UE 5.8 download started in the Epic Launcher | in progress |
| 11:32 | `make_test_wavs.sh` made 3 clips (4.77 s, 6.07 s, 4.55 s; 48 kHz int16 mono) | ✅ [measured] |
| 11:32 | `play_to_device.py` played clip1 to the built-in speakers: 4.77 s clip in 5.31 s wall time (about 0.5 s device open/drain overhead) | ✅ [measured] |
| ~11:50 | BlackHole 2ch installed with `brew install --cask blackhole-2ch`; loaded via `sudo killall coreaudiod` with no reboot | ✅ [measured] |
| ~11:50 | BlackHole device: 2 in / 2 out, 48 000 Hz default | ✅ [measured] |
| ~11:50 | Loopback test: played clip1 into BlackHole and recorded from BlackHole at the same time (`sd.playrec`). Recorded peak 0.785 = source peak 0.785, RMS 0.159, so the signal arrives bit-exact. Measured offset 256 ms, but that includes sounddevice's play+record stream buffering; it is **not** BlackHole's own latency, which is about 0 ms by design. [estimate] | ✅ [measured] |
| 12:02 | UE 5.8.3 installed (CL 58210709), 43 GB | ✅ [measured] |
| 12:08 | First launch failed: missing Xcode Metal Toolchain, fixed with `xcodebuild -downloadComponent MetalToolchain` | ✅ |
| 12:12 | Editor launched; official Unreal MCP listening on 127.0.0.1:8000 about 30 s after launch; ~40 toolsets incl. MetaHumanToolset | ✅ [measured] |
| 12:21 | In-editor Python via PyJobs runner (Python Remote Execution multicast fails on macOS loopback) | ✅ |
| 12:21 | `GetAudioDevices` lists **BlackHole 2ch** (`audcap://BlackHole2ch_UID`); offers 13 formats, 8 kHz to 768 kHz, incl. 48 kHz/2 ch | ✅ [measured] |
| 12:22 | `CreateAudioSubject` from Python fails: the `FLiveLinkSourceHandle` returned to Python is empty (C++ shared pointer not marshalled). Create the source in the Live Link UI or a Blueprint instead. | ❌ known limitation |
| 12:23 | MetaHuman Character `/Game/MH/MHC_Default` created via MCP `MetaHumanToolset.create` | ✅ |
| 12:23–12:26 | `try_add_object_to_edit` → 178 body-mesh builds, memory exhaustion (swap 10/11 GB), editor hung, force-quit by user | ❌ blocker on 16 GB |

## Acceptance criteria

| # | Criterion | Status |
|---|---|---|
| 1 | UE 5.8 launches on macOS | ✅ |
| 2 | Default MetaHuman renders | ⏳ |
| 3 | External audio reaches Audio Live Link | 🟡 BlackHole visible to the MetaHuman audio API; subject not yet created |
| 4 | MetaHuman visibly speaks | ⏳ |
| 5 | Three consecutive clips work | ⏳ |
| 6 | Results and blockers documented | in progress |
| + | Mood switching | ⏳ |

## Measurements (to fill in)

- Audio device config:
- Editor FPS, idle and while speaking (Show FPS / `stat unit`):
- CPU/GPU (Activity Monitor → GPU History, `sudo powermetrics --samplers gpu_power`):
- Lip lag vs. audible speech (record the screen with audio and count frames from audio onset to mouth opening):
- Stability (repeat count, crashes):
- macOS-specific issues:
