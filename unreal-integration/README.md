# Unreal integration: MetaHuman Audio Live Link on macOS

Milestone 1B: make a default MetaHuman lip-sync to external speech audio using Epic's native **MetaHuman (Audio)** Live Link source in UE 5.8 on macOS. No Audio2Face.

| Doc | Contents |
|---|---|
| `macos_compatibility.md` | Measured machine specs compared with Epic's 5.8 requirements, plus decisions |
| `ue58_setup.md` | Launcher install steps (include MetaHuman Creator Core Data) and project location |
| `metahuman_setup.md` | Creating and placing a default MetaHuman, binding the Live Link subject |
| `audio_live_link_setup.md` | BlackHole, mic permission, Live Link source, **interface contract for the Python bridge** |
| `mood_test.md` | Mood/intensity tests and the emotion receiver component plan |
| `unreal_mcp_notes.md` | MCP status; Python/manual fallback |
| `test_results.md` | Log, acceptance criteria, measurements |
| **`WINDOWS_HANDOFF.md`** | **Start here on the Windows PC**: verified APIs, gotchas, setup and steps |

## Layout

```
unreal-integration/
├── scripts/
│   ├── make_test_wavs.sh             # 3 speech clips, 48 kHz mono WAV (macOS `say`)
│   ├── play_to_device.py             # play WAVs to a named CoreAudio device (e.g. BlackHole 2ch)
│   ├── create_project.sh             # Blueprint-only UE 5.8 project with verified plugin list
│   └── ue/introspect_metahuman_api.py  # dumps the installed MetaHuman/Live Link Python API
├── test_audio/                       # generated clips
└── .venv/                            # sounddevice, soundfile, numpy (gitignored)
```

Unreal project, kept outside git because of its size: `~/Documents/Unreal Projects/GradiumMH/`.

## Quick start

```bash
cd unreal-integration
python3 -m venv .venv && .venv/bin/pip install sounddevice soundfile numpy
./scripts/make_test_wavs.sh
brew install --cask blackhole-2ch          # asks for your password
./scripts/create_project.sh                # after UE 5.8 is installed
.venv/bin/python scripts/play_to_device.py --device "BlackHole 2ch" test_audio/clip*.wav
```

Secrets such as `GRADIUM_API_KEY` go in the repo-root `.env` (gitignored; see `.env.example`).
