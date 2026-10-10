# macOS compatibility: UE 5.8 + MetaHuman

Inspected 2026-10-10 on the dev machine. Every value below was **measured** with `system_profiler`, `sw_vers`, `df` and `xcodebuild`.

## Machine

| Item | Value |
|---|---|
| Model | MacBook Air (Mac17,4) |
| Chip | Apple M5, 10-core CPU (4 Super + 6 Efficiency), 10-core GPU |
| GPU API | Metal 4 |
| RAM | 16 GB unified |
| Disk free | 163 GiB on the Data volume |
| macOS | 26.5.1 (build 25F80) |
| Xcode | 26.6 (17F113), active at `/Applications/Xcode.app` |
| Python | 3.11.8 (system framework), Homebrew present |
| Audio in | MacBook Air mic (1 ch), iPhone Continuity mic, plus Zoom/Teams/WeMeet/Immersed virtual devices |
| Virtual loopback | **BlackHole not installed** (see `audio_live_link_setup.md`) |

## Compared with Epic's UE 5.8 macOS requirements

Source: [macOS Development Requirements, UE 5.8](https://dev.epicgames.com/documentation/en-us/unreal-engine/macos-development-requirements-for-unreal-engine)

| Requirement | Epic says | This Mac | Status |
|---|---|---|---|
| macOS minimum | Sonoma 14.5 | 26.5.1 | OK |
| macOS recommended | "Latest Sequoia 15" | 26.5.1 (Tahoe) | ⚠️ **Newer than any version Epic lists.** Not officially validated. |
| CPU | Min M1/M2, rec. M3 | M5 | OK |
| RAM | Min 16 GB, rec. 32 GB+ | 16 GB | ⚠️ **At the minimum.** MetaHuman assets plus shader compilation will be memory-tight. |
| GPU | Metal 1.2 | Metal 4 | OK |
| Nanite / VSM | M2+ (Beta) | M5 | OK (beta) |
| Lumen HWRT / MegaLights | M2+ (Experimental) | M5 | Experimental, avoid |
| Xcode | Rec. 26.1.1, min 26.0; **26.4 explicitly incompatible** | 26.6 | ⚠️ **Not listed as either compatible or incompatible.** |

## Decisions

- **Xcode:** leave 26.6 as it is; don't downgrade. The project is **Blueprint and Python only**, so no C++ compile and therefore no Xcode toolchain dependency. If a C++ plugin is ever needed, install Xcode 26.1.1 side by side as `Xcode_26.1.1.app` and switch with `xcode-select`. Never replace the main `Xcode.app`.
- **16 GB RAM:** use the MetaHuman's lower LODs in the viewport, turn off Lumen HWRT, close browsers and Electron apps while testing, and let shader compilation finish before measuring FPS.
- **macOS 26:** record any Metal or driver-level issues in `test_results.md`, since this OS isn't on Epic's list.

## MetaHuman on Mac (from Epic docs)

- Since UE 5.7, MetaHuman Creator runs in-editor on Windows, Mac and Linux.
- On Mac, creating **Identity and Performance** assets (MetaHuman Animator) is disabled because marker tracking needs DX12. "Conform from Identity" is unavailable. Neither is needed here.
- The MetaHuman (Audio) Live Link source accepts "any connected USB (UVC compliant) audio capture device supported by Windows or macOS." A CoreAudio virtual device like BlackHole shows up as a normal input device, so it is expected to work. **To be verified** in `test_results.md`.

## Issues hit during setup

| Issue | Fix |
|---|---|
| First editor launch failed: `Xcode Metal Compiler error: cannot execute tool 'metal' due to missing Metal Toolchain`. Xcode 26 ships the Metal compiler as a separate component, and UE needs it to compile shaders even for Blueprint-only projects. | `xcodebuild -downloadComponent MetalToolchain` (688 MB, no sudo). Verify with `xcrun -sdk macosx metal --version` → `Apple metal version 32023.883`. |
| BlackHole cask said a reboot was required | `sudo killall coreaudiod` was enough |
| Launcher started UE 5.8 without the `metahuman_content` tag (MetaHuman Creator Core Data) | Library → 5.8 ▾ → Options → tick MetaHuman Creator Core Data → Apply |
| **Editor hang (16 GB RAM):** `MetaHumanCharacterEditorSubsystem.try_add_object_to_edit()` on a fresh MetaHuman Character built 178 body meshes (`BodyMesh_5…359`) on the game thread (frame 115) in about 3 min. Each AssetCompile requested about 4–4.6 GB against a MemoryLimit of about 1.8 GB, and swap hit 10/11 GB. The editor stopped responding and was force-quit. [measured, from GradiumMH.log] | Don't open MetaHuman Creator editing on this Mac. Use a pre-assembled MetaHuman (Fab) or assemble on a 32 GB+ machine. Never run blocking MetaHuman calls through PyJobs. |
