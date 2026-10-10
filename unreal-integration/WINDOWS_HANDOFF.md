# Windows handoff: continue milestone 1B on the Windows PC

The Mac (M5, 16 GB) work stopped at MetaHuman creation, which ran out of memory. Windows is Epic's **fully supported** MetaHuman platform, so continue there.

**If you're Claude Code on Windows:** read this file, then `test_results.md` and `macos_compatibility.md`. Don't redo anything marked ✅. Same rules as before: use only APIs that are verified in the installed engine, never invented nodes, and the official Unreal MCP plugin. No Audio2Face, and no Claude API yet.

## Goals on Windows, in order

1. ✅ **Assemble an animation-ready default MetaHuman**, the Mac blocker. Full rig (joints + blend shapes), UE Cine.
2. ✅ **Run the lip-sync test** (acceptance criteria 2–5) on Windows directly. 270 ms audio → jaw with WASAPI, ~80 FPS.
3. ⏳ **Export the MetaHuman for the Mac** with the UE Optimized build, so the Mac can try rendering it too (optional, not done).
4. ✅ Mood switching (Phase 4) through the Python API.
5. ✅ **Voice MVP:** `dt/bridge/avatar_chat.py` (mic → Gradium STT → Gemini → Gradium TTS → face). See `bridge/README.md`.

## What is already verified (from the installed UE 5.8.3 on Mac, same engine version)

| Fact | Source |
|---|---|
| Plugins needed: `LiveLink, LiveLinkControlRig, MetaHumanCoreTech, MetaHumanLiveLink, MetaHumanCharacter, MetaHuman, MetaHumanSDK, RigLogic, PythonScriptPlugin, EditorScriptingUtilities, AudioCapture, ModelContextProtocol, ToolsetRegistry, AllToolsets, MetaHumanGenerator` | `.uplugin` files in the engine |
| Official Unreal MCP: endpoint `http://127.0.0.1:8000/mcp`, launch flag `-ModelContextProtocolStartServer`, tool search meta-tools `list_toolsets` / `describe_toolset` / `call_tool` | Epic docs + measured |
| MCP `metahuman_toolset.metahuman.MetaHumanToolset` has `create(asset_path)`, `begin_edit`, `end_edit`, `get/set_body_shape`, `get/set_skin_tone`, `get/set_eye_color` | engine `MetaHumanGenerator/Content/Python/metahuman_toolset/metahuman.py` |
| `unreal.MetaHumanCharacterEditorSubsystem`: `try_add_object_to_edit`, `request_texture_sources`, `request_auto_rigging` (`EMetaHumanRigType`: JointsOnly / JointsAndBlendShapes), `can_build_meta_human`, `build_meta_human` (`FMetaHumanCharacterEditorBuildParameters.PipelineType`: Cinematic = "UE Cine (Complete)", Optimized = "UE Optimized", UEFN; `PipelineQuality`: Low / Medium / High / Cinematic) | `MetaHumanCharacterEditorSubsystem.h`, `MetaHumanCharacterBuild.h` |
| Audio Live Link Blueprint library `UMetaHumanLocalLiveLinkSourceBlueprint`: `GetAudioDevices`, `GetAudioTracks`, `GetAudioFormats`, `CreateAudioSource`, `CreateAudioSubject`, `GetSubjectSettings` | `MetaHumanLocalLiveLinkSourceBlueprint.h` |
| Subject settings `UMetaHumanAudioBaseLiveLinkSubjectSettings`: **`SetMood` / `GetMood`, `SetMoodIntensity` / `GetMoodIntensity` (0–1), `SetLookahead` / `GetLookahead` (80–240 ms)**, all BlueprintCallable. Default mood = AutoDetect. | `MetaHumanAudioBaseLiveLinkSubjectSettings.h` |
| `EAudioDrivenAnimationMood`: AutoDetect(255), Neutral, Happiness, Sadness, Disgust, Anger, Surprise, Fear, Confidence, Excitement, Boredom, Playfulness, Confusion | `SpeechAnimationSolverTypes.h` |

## Known gotchas (learned the hard way on the Mac)

1. **`CreateAudioSubject` doesn't work from Python.** The `FLiveLinkSourceHandle` that comes back from `create_audio_source()` is empty in Python because the C++ shared pointer isn't marshalled. Create the source in the **Live Link panel** (or a Blueprint graph). Python is fine for `get_subject_settings` and mood/lookahead.
2. **Pick the 48 kHz audio format**, not the first one in the list. Formats are listed highest rate first (768 kHz …), and subject creation fails on those.
3. **Don't run blocking MetaHuman calls through a script on the game thread** without watching the log. `try_add_object_to_edit` built 178 body meshes in a loop on the Mac. The normal MetaHuman Creator UI is safer.
4. MetaHuman texture synthesis and auto-rigging are **Epic cloud services**, so be signed in to your Epic account in the editor.
5. The Xcode/Metal fix is Mac-only; Windows uses DX12.

Learned on Windows (2026-10-10, all fixed or worked around; details in `test_results.md`):

6. **Shader Model 6 is required** for the MetaHuman skin (see the ini above).
7. **PyJobs re-entrancy:** long operations (save, assembly) pump Slate, which used to re-run the same job nested inside itself and crashed assembly ("Window Creation Failed"). `init_unreal.py` now has a busy guard and claims jobs as `.running`. Blocking calls such as `build_meta_human` are fine through PyJobs now.
8. **Windows PowerShell 5.1 mangles JSON arguments.** Give `mcp_call.py` JSON on stdin (`-`) or `@file`, or use Git Bash.
9. **Live Link sources don't survive an editor restart.** The preset `/Game/LiveLink/LLP_MH_Audio` + `DefaultLiveLinkPreset` handles that.
10. **Use WASAPI to write into CABLE Input.** MME (sounddevice's first match) added about 195 ms (465 vs 270 ms audio → mouth).
11. **The VB-Cable installer makes CABLE Input/Output the Windows defaults.** Set your real devices back as the defaults.
12. **UI-only steps can be automated:** MCP `SlateInspectorToolset` (Snapshot → Click/Type). It was used for the Live Link source and the project-settings prompt. The texture-download dropdown didn't respond; `request_texture_sources()` from Python did the same job.
13. **Never `SlateInspector.Screenshot` a widget that is off-screen.** It crashes the editor (D3D12 backbuffer copy assertion).
14. **The demo character is Vivian** (`/Game/MH/MHC_Vivian` → `BP_MHC_Vivian`, actor `MH_Avatar`). Any of the 29 bundled presets works the same way: `EditorAssetLibrary.duplicate_asset('/MetaHumanCharacter/Optional/Presets/<Name>', '/Game/MH/MHC_<Name>')`, open it, `request_auto_rigging` + `request_texture_sources`, `build_meta_human`, save. About 3 minutes in total.
15. **Never call `save_dirty_packages()` unfiltered.** Read-only MCP `BlueprintTools` queries on engine assets mark them dirty, and saving writes into the UE install (this happened to `ABP_Face`). Save only `/Game/...` packages (`EditorAssetLibrary.save_asset(path)`).
16. **After recompiling an AnimBP**, the running instance in the editor level can keep the old graph. Re-set it with `comp.set_anim_instance_class(None)` and then the class.

## Setup on Windows

### 1. Engine

Epic Games Launcher → Unreal Engine → Library → install **5.8**. Under **Options**, tick **MetaHuman Creator Core Data**. On the Mac it was *not* ticked by default, so check it.

### 2. Repo and Python

```powershell
git clone entire://aws-eu-central-1.entire.io/et/icvrhackathon/dt   # needs Entire's git helper
cd dt\unreal-integration
py -3 -m venv .venv
.venv\Scripts\pip install sounddevice soundfile numpy
```

The test clips are already committed in `test_audio/clip{1,2,3}.wav` (48 kHz mono). `make_test_wavs.sh` is macOS-only, but you don't need it.

The Gradium key isn't in git: copy `.env` from the Mac, or create `dt\.env` from `.env.example`.

### 3. Project (`create_project.sh` / `launch_editor.sh` are bash/macOS; do this instead)

Create `%USERPROFILE%\Documents\Unreal Projects\GradiumMH\GradiumMH.uproject`:

```json
{
  "FileVersion": 3,
  "EngineAssociation": "5.8",
  "Description": "Gradium hackathon - MetaHuman Audio Live Link test",
  "Plugins": [
    { "Name": "LiveLink", "Enabled": true },
    { "Name": "LiveLinkControlRig", "Enabled": true },
    { "Name": "MetaHumanCoreTech", "Enabled": true },
    { "Name": "MetaHumanLiveLink", "Enabled": true },
    { "Name": "MetaHumanCharacter", "Enabled": true },
    { "Name": "MetaHuman", "Enabled": true },
    { "Name": "MetaHumanSDK", "Enabled": true },
    { "Name": "RigLogic", "Enabled": true },
    { "Name": "PythonScriptPlugin", "Enabled": true },
    { "Name": "EditorScriptingUtilities", "Enabled": true },
    { "Name": "AudioCapture", "Enabled": true },
    { "Name": "ModelContextProtocol", "Enabled": true },
    { "Name": "ToolsetRegistry", "Enabled": true },
    { "Name": "AllToolsets", "Enabled": true },
    { "Name": "MetaHumanGenerator", "Enabled": true }
  ]
}
```

Create `...\GradiumMH\Config\DefaultEngine.ini`, pointing the path at your clone:

```ini
[/Script/PythonScriptPlugin.PythonScriptPluginSettings]
+AdditionalPaths=(Path="C:/path/to/dt/unreal-integration/scripts/ue")
bDeveloperMode=True

[/Script/Engine.RendererSettings]
r.GPUSkin.Support16BitBoneIndex=True
r.GPUSkin.UnlimitedBoneInfluences=True
r.SkinCache.CompileShaders=True
r.AllowStaticLighting=False
r.Shadow.Virtual.Enable=1

[/Script/WindowsTargetPlatform.WindowsTargetSettings]
DefaultGraphicsRHI=DefaultGraphicsRHI_DX12
-D3D12TargetedShaderFormats=PCD3D_SM5
+D3D12TargetedShaderFormats=PCD3D_SM6

[/Script/MacTargetPlatform.MacTargetSettings]
-TargetedRHIs=SF_METAL_SM5
+TargetedRHIs=SF_METAL_SM6
```

The SM6 lines matter. A hand-made project otherwise runs at SM5 (BaseEngine default), the MetaHuman skin bake fails with "maximum ps_5_0 sampler register index (16) exceeded", and the head comes out grey. The renderer lines are what the MetaHuman editor asks for. **The Mac project needs the same additions**, since `create_project.sh` didn't write them before. And `Config/DefaultGame.ini` restores the Live Link source at startup:

```ini
[/Script/LiveLink.LiveLinkSettings]
DefaultLiveLinkPreset=/Game/LiveLink/LLP_MH_Audio.LLP_MH_Audio
```

That loads `scripts/ue/init_unreal.py` (the PyJobs runner) at startup, which makes `python scripts\ue_exec.py -c "..."` work. `ue_exec.py` defaults to `~/Documents/Unreal Projects/GradiumMH`; set `PROJ_DIR` if you put the project elsewhere. On Windows, Epic's Python Remote Execution may also work, but PyJobs is already proven.

Launch with MCP (`scripts\launch_editor.ps1` does this, after checking that port 8000 is free):

```powershell
& "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "$env:USERPROFILE\Documents\Unreal Projects\GradiumMH\GradiumMH.uproject" -ModelContextProtocolStartServer -ModelContextProtocolPort=8000
```

Check it with `python scripts\mcp_call.py list_toolsets`. Windows PowerShell 5.1 strips the double quotes from JSON passed as an argument to a native program, so give `mcp_call.py` its JSON on stdin (`... | python scripts\mcp_call.py call_tool -`) or from a file (`call_tool @args.json`). The repo's `.mcp.json` registers `unreal-mcp` for Claude Code when it's started from the `dt\` folder; run `/mcp` to reconnect after the editor is up.

### 4. Virtual audio cable (Windows equivalent of BlackHole)

Install **VB-Audio Virtual Cable** (free, vb-audio.com), then reboot or replug.

- Playback device **"CABLE Input"** (where the bridge and WAVs play to) → recording device **"CABLE Output"** (what Unreal listens to).
- In Sound settings, set both to **48 000 Hz**: Properties → Advanced → 2 channel, 16-bit, 48000 Hz. (Pack45 already defaulted to 2 ch, 48 000 Hz, 24-bit on this PC.)
- **The installer makes CABLE Input/Output the Windows default playback and recording devices.** Set your real devices back as the defaults, or your speakers go silent and Unreal's own editor audio leaks into the lip-sync input.

```powershell
.venv\Scripts\python scripts\play_to_device.py --list
.venv\Scripts\python scripts\play_to_device.py --device "CABLE Input" test_audio\clip1.wav test_audio\clip2.wav test_audio\clip3.wav --gap 1.5
```

Tell your teammate: on Windows the bridge plays to **"CABLE Input"**. On the Mac it's **"BlackHole 2ch"**. Everything else in the contract (48 kHz, 2 ch) is the same.

### 5. Live mic from the Mac on site (over the VPN)

Don't use the remote-desktop mic: it's compressed and its delay varies. Stream raw PCM over UDP instead:

```powershell
# PC: plays whatever arrives into CABLE Input, and silence otherwise (stream never closes)
.venv\Scripts\python scripts\audio_recv.py            # UDP 50555; allow python through Windows Firewall (Private)
```
```bash
# Mac: default mic -> PC (use the PC's VPN/LAN IP)
.venv/bin/python scripts/audio_send.py --host <PC_IP>
.venv/bin/python scripts/audio_send.py --host <PC_IP> --wav test_audio/clip1.wav   # network test without a mic
```

The format is 48 kHz int16 mono in 10 ms packets, with a 40 ms jitter buffer (`--prefill`) and latency capped at 150 ms (`--max-buffer`). The receiver prints `rx/lost/late/underruns/buffer` every 5 s. On the Mac over loopback into BlackHole, a sent WAV came back bit-exact (correlation 1.000, 477/477 packets, 0 lost) [measured]. VPN latency has not been measured yet. Measure lip lag from a screen recording made **on the PC**, not through the remote viewer.

**Conversation instead of plain lip-sync:** to *talk to* Vivian from the Mac, don't run `audio_recv.py` on the PC. Run `bridge\chat.ps1 -Remote <MAC_IP>`: the bridge takes the `audio_send.py` stream as its mic and sends her voice back to the Mac's `audio_recv.py --port 50556`. See `bridge/README.md`.

## Step-by-step on Windows

1. **MetaHuman:** create `/Game/MH/MHC_Default`. You can use MCP: `'{"toolset_name":"metahuman_toolset.metahuman.MetaHumanToolset","tool_name":"create","arguments":{"asset_path":"/Game/MH/MHC_Default"}}' | python scripts\mcp_call.py call_tool -`, or the Content Browser right-click menu. Open it in **MetaHuman Creator** (the UI), pick a preset, then request textures and the **auto-rig**. Prefer **Joints and Blend Shapes** for better lip-sync; JointsOnly is lighter.
2. **Assemble:** use the **UE Cine (Complete)** pipeline for the Windows test. For the Mac export, assemble a second time with **UE Optimized, Medium or High**.
3. **Level:** create `/Game/Maps/L_AudioTest`, drag in the assembled MetaHuman Blueprint, and add a camera about 60 cm from the face. Verify it with MCP `EditorToolset.EditorAppToolset.CaptureViewport`.
4. **Audio source (UI, see gotcha 1):** Window → Virtual Production → Live Link → **+ Source → MetaHuman (Audio)**. Set Audio Device to **CABLE Output**, choose the **48 kHz** format if asked, set Subject Name to `MH_Audio`, then click **Connect** and look for the green tick.
5. **Bind** ✅ verified: on the placed `BP_MHC_Default` actor set `UseLiveLink = true`, `UseARKit = false`, `LiveLinkSubject = MH_Audio`. The construction script then gives the Body a `LiveLinkInstance`, and the Face (`ABP_Face`) follows. It animates in the editor viewport without PIE. Details in `metahuman_setup.md`.
6. **Test:** first speak into a physical mic (a second source on the mic), then play the three clips into CABLE Input. Record the following in `test_results.md`, separating [measured] from [estimate]:
   - whether the mouth moves
   - whether animation stays continuous
   - whether all 3 clips work
   - lag between audio and mouth (screen recording, count frames)
   - FPS (`stat fps` / `stat unit`)
   - any crashes
7. **Mood:** `python scripts\ue_exec.py -c "import unreal; LL=unreal.LiveLinkBlueprintLibrary; print([str(s) for s in LL.get_live_link_subjects(True, True)])"` lists subject keys. Then use `unreal.MetaHumanLocalLiveLinkSourceBlueprint.get_subject_settings(key)` → `.set_mood(unreal.AudioDrivenAnimationMood.HAPPINESS)` / `.set_mood_intensity(0.8)` during continuous speech. Helpers are in `scripts/ue/mh_audio_livelink.py` (`settings()`, `set_mood()`); pass the key explicitly. Results go in `mood_test.md`.
8. **Export to the Mac (optional):** in the Content Browser, right-click the Optimized MetaHuman folder → **Migrate** (dependencies are included) → a temporary empty UE 5.8 project → zip its `Content` → on the Mac, unzip into `~/Documents/Unreal Projects/GradiumMH/Content`, keeping the same folder paths.

Commit doc and script updates to the repo (not the Unreal project, which is too big). Leave a short note in `test_results.md` saying which machine each result came from.
