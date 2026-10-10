# Test results

Each value is tagged **[measured]** or **[estimate]**.

## Environment [measured]

- **Mac:** see `macos_compatibility.md`. MacBook Air M5, 16 GB, macOS 26.5.1, Xcode 26.6.
- **Windows PC:** Intel i9-12900KF (16 cores / 24 threads), 32 GB RAM, NVIDIA RTX 3080 Ti 12 GB (driver 595.95), Windows 11 Pro 10.0.26200, 760 GB free on C:. UE 5.7 also installed side by side. Python 3.13.5.

## Log (Mac)

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

## Log (Windows PC)

| Time (2026-10-10) | Step | Result |
|---|---|---|
| 11:04 | UE 5.8 install started in the Epic Launcher with InstallTags `templates`, `engine_source`. **`metahuman_content` (MetaHuman Creator Core Data) was not selected**, as on the Mac. [measured, EpicGamesLauncher.log] User will add it via Options after the install. | ⏳ |
| 13:05 | UE 5.8 install still in progress (19.4 GB staged) | in progress |
| 13:05 | `.venv` (Python 3.13.5): sounddevice 0.5.6, soundfile 0.14.0, numpy 2.5.3 | ✅ [measured] |
| 13:05 | Audio: VB-Audio Virtual Cable **not installed yet**. No physical mic among the active input endpoints, only Oculus/VIVE/Pico virtual mics. | ⏳ [measured] |
| 13:08 | Windows PowerShell 5.1 strips the quotes from JSON passed as a native-exe argument (`'{"a":"b c"}'` arrives as `{a:b c}`), and piping adds a UTF-8 BOM. `mcp_call.py` now takes JSON on stdin (`-`) or from `@file`, and strips the BOM. | ✅ fixed |
| 13:10 | `GradiumMH.uproject` + `Config/DefaultEngine.ini` created under `Documents\Unreal Projects\GradiumMH` (PyJobs path → this clone). Port 8000 free. | ✅ |
| 13:15 | Mic: the Realtek Microphone, FrontMic and Line In jacks report UNPLUGGED. A mic must be plugged in (or use the Quest's mic via "Headset Microphone (Oculus Virtual Audio Device)") for the physical-mic test. | ⏳ [measured] |
| 13:16 | VB-Cable Driver Pack45 installed (`VBCABLE_Setup_x64.exe -i -h`, elevated; installer and driver have valid signatures). Endpoints were active **without a reboot**: playback "CABLE Input", "CABLE In 16ch"; recording "CABLE Output". | ✅ [measured] |
| 13:17 | Device format of CABLE Input and CABLE Output: **2 ch, 48 000 Hz**, 24-bit (handoff said 16-bit; the rate is what the contract needs). | ✅ [measured] |
| 13:17 | **The VB-Cable install made CABLE Input/Output the Windows default for all roles** (console, multimedia, comms). Restored to the previous defaults, Oculus Headphones and Headset Microphone. | ✅ fixed |
| 13:19 | Loopback (WASAPI shared, 48 kHz): played clip1 into CABLE Input and recorded CABLE Output at the same time. Run 1: correlation 0.996, with one short glitch. Run 2: correlation 1.000, max sample diff 0.014, source peak 0.785 = recorded peak 0.785. The offset of 111–122 ms includes sounddevice's play+record stream buffering. | ✅ [measured] |
| 13:19 | `dt\.env` created with `GRADIUM_API_KEY` (gitignored) | ✅ |
| 13:21 | Physical mic: **Jabra Evolve 65** USB headset plugged in. Windows made it the default for all roles, which is fine since editor audio now goes to the headset, not the cable. The hardware mic format is 1 ch, 16 kHz, 16-bit; in WASAPI shared mode it is offered at 48 kHz, 2 ch. | ✅ [measured] |
| 13:21 | Jabra level check (8 s): noise floor −82 to −92 dBFS; activity −43 to −66 dBFS, peak 0.174. It picks up sound, but quietly for speech: raise the mic level or move the boom closer if Live Link reacts weakly. | ✅ [measured] |
| 13:22 | UE 5.8 editor binaries present (31 GB). User adding MetaHuman Creator Core Data via Options. | ✅ |
| 13:33 | Editor up (5.8.3, D3D12) with MCP after 74 s: 53 toolsets, incl. `SlateInspectorToolset` (clicks/types in editor UI) and `EditorAppToolset.CaptureViewport`. PyJobs works. | ✅ [measured] |
| 13:35 | `GetAudioDevices`: CABLE Output, Jabra, Oculus, Pico, VIVE. **Each offers exactly one format, 48 000 Hz / 2 ch** (no 768 kHz trap on Windows). | ✅ [measured] |
| 13:35 | `/Game/MH/MHC_Default` created via MCP `MetaHumanToolset.create`; opened with `EditorAppToolset.OpenEditorForAsset`. Only 3 body-mesh builds (Mac: 178). Editor 8.9 GB. | ✅ [measured] |
| 13:36 | "Missing Project Settings" notification → **Enable Missing**: `r.GPUSkin.Support16BitBoneIndex`, `r.GPUSkin.UnlimitedBoneInfluences`, `r.SkinCache.CompileShaders` (restart needed). | ✅ |
| 13:37 | **Create Full Rig** (Joints and Blend Shapes). The toolkit warns below 10 GiB available virtual memory (commit limit was 33.7 GB with a 2 GB page file); it continued. First cloud call opened a browser for Epic device-code login. **Auto-rig finished in 50.7 s.** Peak editor 14.8 GB. | ✅ [measured] |
| 13:39 | Textures: the UI "Download Texture Sources" dropdown didn't react to a synthesized click, so `request_texture_sources(report_progress=True)` from Python: body 5.9 s, face 10.5 s (2k). Asset saved (144 MB). | ✅ [measured] |
| 13:42 | `build_meta_human` (Cinematic) from PyJobs **crashed the editor**: "Window Creation Failed (Error Code 87)". Cause: PyJobs re-entrancy. Save/assembly progress dialogs pump Slate, which re-fired the tick callback and re-ran the same job nested (log: SavePackage ×5 in one frame, face mesh built 3×, 51-deep script stack). **Fixed `init_unreal.py`**: busy guard + jobs claimed as `.running` before exec. | ✅ fixed |
| 13:49 | Assembly retry: **succeeded in 189.5 s**; 49 packages, 568 MB under `/Game/MH/Unpacked/MHC_Default/`. Peak editor 16.9 GB, commit 35.9 GB (page file grew the limit to 38.8 GB). | ✅ [measured] |
| 13:51 | Level `/Game/Maps/L_AudioTest` (Template_Default); `BP_MHC_Default` placed as `MH_Default`; `CAM_Face` CineCamera at (0, 73, 157), yaw −90 (face looks +Y, nose tip at z≈157), 35 mm, focus 62 cm. | ✅ |
| 13:52 | Live Link source created in the UI (driven by SlateInspector): **+ Add → MetaHuman (Audio)**; Audio Device defaulted to CABLE Output, format "IEEE Float 2 channels @ 48000 Hz"; Subject Name `MH_Audio` (under *Advanced*) → **Connect**. Subject role "Basic". `get_subject_settings` from Python works (mood AutoDetect, intensity 1.0, lookahead 80). | ✅ |
| 13:53 | **Binding verified**: `BP_MHC_Default` has variables `UseLiveLink`, `LiveLinkSubject`, `UseARKit`. On the placed actor: `UseLiveLink=True`, `UseARKit=False`, `LiveLinkSubject=MH_Audio` → Body anim class `LiveLinkInstance`, Face `ABP_Face`, both update in editor (no PIE needed). | ✅ |
| 13:54 | Renders, but **skin grey**: project ran D3D12 **SM5** (BaseEngine default; the hand-made project lacked the template's SM6 lines), and `M_skin_unified_UI` failed: "maximum ps_5_0 sampler register index (16) exceeded". Added the TP_BlankBP renderer/SM6 settings; re-assembled on SM6 in 64.8 s (VT textures, head base color mean RGB 137/92/70). | ✅ fixed |
| 14:00 | Live Link sources don't survive an editor restart. Saved `/Game/LiveLink/LLP_MH_Audio` (preset) and set it as `DefaultLiveLinkPreset` in `DefaultGame.ini` (applied at startup; not yet verified across a restart). | 🟡 |
| 14:02 | **Lip-sync**: during clips `CTRL_expressions_jawOpen` on the body's LiveLinkInstance and `head_lod0_mesh__jaw_open` on the face rig carried the same values. | ✅ [measured] |
| 14:03 | `lipsync_latency.py` (per-frame curve log, MME output): 77 FPS, no hitches; jawOpen silence mean 0.149 vs speech max 0.554; curve changed every frame during speech; **lag 465 ms** (xcorr r = 0.63). | ✅ [measured] |
| 14:04 | Same with **WASAPI output: lag 270 ms** (first jaw movement 259–317 ms after `play()`), 79 FPS. `play_to_device.py` now defaults to WASAPI on Windows. | ✅ [measured] |
| 14:05 | Visual: 5 viewport captures during clip2 vs silence: mouth-region change 6.5–11.2 (silence-to-silence 1.1); open "O", teeth visible. | ✅ [measured] |
| 14:06 | Moods via Python during speech: Happiness → `mouthCornerPullL` mean 0.349 (Neutral 0.012, Sadness 0.036); lip-sync unaffected (lag 255–260 ms). See `mood_test.md`. | ✅ [measured] |
| 14:10 | **Voice MVP** (`dt/bridge/avatar_chat.py`): Gradium STT → Gemini → Gradium TTS → CABLE Input. End-to-end from a WAV "visitor": transcript exact; reply with `[excited]` mood; face jaw up to 0.64 and smile 0.1–0.28 during the reply, idle while the visitor spoke. | ✅ [measured] |

| 14:18 | MCP `SlateInspectorToolset.Screenshot` on a list item scrolled off-screen (negative y) **crashed the editor** (D3D12 assertion "Source height out of bounds… BackBuffer"). Only screenshot whole windows or on-screen widgets. | ❌ lesson |
| 14:19 | Restart: **`DefaultLiveLinkPreset` works**. Log "Applied 'LiveLinkPreset LLP_MH_Audio'", and `MH_Audio` exists at startup with no UI steps. | ✅ [measured] |
| 14:20 | **Vivian**: duplicated preset `/MetaHumanCharacter/Optional/Presets/Vivian` → `/Game/MH/MHC_Vivian` (29 presets ship with hair, brows, lashes, peach fuzz, garment). Python `request_auto_rigging(JOINTS_AND_BLEND_SHAPES)` 27.7 s + `request_texture_sources` 6.5/10.3 s; assembled (UE Cine) in 102.6 s. Placed as `MH_Avatar` (old `MH_Default` removed; assets kept) with the same Live Link binding; grooms Hair_S_BobLayered, Eyebrows_M_SlightArch, Peachfuzz, Eyelashes_L_ThickCurl. `CAM_Face` at (0, 95, 163), 35 mm. | ✅ |
| 14:24 | Vivian lip-sync: 120 FPS median, jaw max 0.65, every frame changes; **lag 330–340 ms** in this editor session (lookahead 80, buffers identical; the previous session gave 255–270). The variance between sessions is unexplained. Bridge headset delay default is now 0.33 s. | ✅ [measured] |
| 14:26 | Voice turn with Vivian + Emma voice + flash-lite: end of turn → reply text 955 ms (Gemini 646 ms), first audio +77 ms; jaw 0.35–0.53 through the reply. | ✅ [measured] |

| 14:35 | User feedback: "lip only moving one way", no emotion, sync off. All solver outputs logged (`record_curves.start(all_curves=True)`) on a vowel-rich sentence: at **lookahead 80** the motion was mostly `mouthLipsPullD` + jaw; funnel max 0.38, lips-together 0.47, and at rest the lower lip was pulled 0.45 and the brows raised 0.25. Face LOD stayed 0 (not an LOD problem). | 🔎 [measured] |
| 14:37 | **Lookahead 240**: lips-together 0.89, stretch 0.49, 56 vs 46 curves moving. Lag rises to ~505 ms (bridge headset delay now 0.50 s). | ✅ [measured] |
| 14:39 | **Neutral-frame calibration** (`capture_neutral_frame_countdown = 5` during silence; the inherited `FMetaHumanRealtimeCalibration` works for audio subjects too): resting lower-lip pull 0.45 → 0, mouth closes at rest. With an `[excited]` reply: jaw up to 0.99, funnel 0.61, closure 0.60, smile 0.49, cheeks 0.3, 67 curves moving. | ✅ [measured] |
| 14:43 | The audio solver **never blinks in silence** (0 blinks in 12 s, with or without calibration, and also with −60/−45/−35 dB room noise). A reply mood persists at rest (Excitement 1.0: brows 0.83) → bridge now switches to Happiness 0.5 while listening (smile 0.15, brows 0.10). | 🔎 [measured] |
| 14:52 | **Procedural blink**: `/Game/MH/ABP_Face_Blink` = copy of `ABP_Face` with Copy Pose From Mesh → **Modify Curve** (`CTRL_expressions_eyeBlinkL/R` → 1.0, Blend, Alpha ← `BlinkAlpha`) → Output; EventGraph: 160 ms triangle every 2–5 s (random). Set as `anim_class` on `MH_Avatar`'s Face. Silence: 3 blinks in 15 s, upper-eyelid joint drops 0.73–0.75 cm per blink (0.02 cm otherwise). Lip-sync unaffected (62 face-rig outputs moving). | ✅ [measured] |

| 14:58 | **Head movement**: existing body loops on `metahuman_base_skel` (head range, local): MHC `mhc_mh001_fmn_b_idle` 45 s, 12/5/14°; `AS_MH_Neutral_Stand_Idle_Loop` 10 s, 3/3/5°; emotion loops 2–7°. None carry curves. New `/Game/MH/ABP_Body_IdleLiveLink`: Sequence Player → **Live Link Pose** (subject `MH_Audio`; evaluates its input pose, then sets curves only for a Basic-role subject) → Output. `BP_MHC_Vivian` construction script now assigns it instead of `LiveLinkInstance`. MHC idle swung the head up to 38° (looking around) → switched to the stand idle loop: **head ≤ 3.6° from its mean, ~3°/s**. | ✅ [measured] |
| 15:00 | After the user's 2.5-min chat, the audio solver **started blinking in silence** (input level 0): 7–12 blinks/12 s, eyes > half-closed 33% of the time. Same with the plain `LiveLinkInstance`, so it's the solver, not the AnimBP. `ABP_Face_Blink` now zeroes the solver's eyeBlinkL/R (Modify Curve, Scale × 0) before the procedural blink: **3 blinks/12 s, eyes closed 2% of the time** (~15/min). | ✅ [measured] |
| 15:01 | Mistake: `save_dirty_packages(False, True)` also re-saved the engine's `/MetaHumanCharacter/Face/ABP_Face` (marked dirty by read-only MCP graph queries). Verified structurally unchanged (same 2 nodes, empty EventGraph, no variables). Epic Launcher → Verify restores the original bytes. | ⚠️ |

| 15:09 | **Mood-matched body loops + talking nods** in `ABP_Body_IdleLiveLink`. AnimGraph: stand idle → Blend(int, 0.6 s) happy_f → Blend sad_f → Blend surprise_m → Live Link Pose → Local→Component → Transform (Modify) Bone `head` (additive, bone space, Rotation ← `HeadOffset`) → Component→Local → Output. Blend Poses by int can't gain pins from MCP/Python (arrays resize, but there's no node reconstruct), so it's a chain of 2-input blends with `SelHappy/SelSad/SelSurprise` computed from `BodyMood` in the EventGraph. Head-bone axes (measured): `HeadOffset.yaw` = nod (+ chin down), `.roll` = turn, `.pitch` = tilt. EventGraph: jawOpen smoothed slow (~0.4 s) and fast (~70 ms); `Talk` with fast attack and slow release; nod = Talk·(1.5·sin(2.3t) + clamp(25·(fast−slow), −3, 6)), turn ±2.5°, tilt ±1.5°. | ✅ |
| 15:11 | Bridge sets `BodyMood` with the face mood (happy/excited/playful/confident → 1, sad → 2, surprised → 3, else 0; listening → 0). End-to-end turn: listening = idle and still; reply (`[excited]`) = happy loop, Talk 0.8–0.88, **nods −4.5…+7.2°**; back to idle afterwards. Silence: no nods, head 3°/s; happy loop alone: 7.7°/s. | ✅ [measured] |

| 15:15 | User feedback: "a big animation transition when she speaks, and she looks back in an awkward way". Measured: the emotion loops' posture differs from the stand idle by **19–26° at neck_01** and 9–13° at the head, so each reply leaned in and swung back. Body loops are now **off by default** (`--body-moods` to re-enable); moods change only the face. Talking nods were busy (2.7 direction reversals/s, peaks 36°/s), so they're calmer now (≈140 ms syllable filter, gain 15, −2…+4°) and eased through `RInterpTo`. | ✅ [measured] |
| 15:22 | **Look at the camera**: an `AnimNode_LookAt` on `head` made the entire body AnimGraph stop evaluating (reference pose, 0 curves, so no lip-sync) even though it compiled cleanly. Removed. Replaced with a second Transform (Modify) Bone on `head` (Replace, World space, Rotation ← `LookRot` = MakeRotFromYX(CamTarget − head, up), Alpha ← `LookAlpha`) before the additive nods. Schedule: ease in 0.5 s, hold 1.5–3.5 s, ease out 0.6 s, every 4–9 s. Pins that MCP can't create (LookAt's `LookAtLocation`) appeared after **Blueprint editor → File → Refresh All nodes** (clicked with SlateInspector). | ✅ |
| 15:27 | Eye contact: her eyes rest **3.8° above** the head's forward axis, so the bridge aims at the camera lowered by distance·tan 3.8°. During looks: eyes ±2.1° sideways (parallax) and −0.3° vertically from the camera; between looks 5–8°. End-to-end turn: `BodyMood` 0 throughout, spine travel ≤ 1.4 cm, looks 10–53% of each 4-s window, 260 curves, nods while speaking. | ✅ [measured] |

| 15:50 | **Streaming LLM → TTS** (A/B, 3 questions × 2 runs, ms from end of speech, medians): old (whole reply, VAD 3 s ×3) LLM first text 1935, in-ear 2624; stream + VAD 2 s ×1: 1220 / 1937, **but VAD 2 s ×1 cut the long question off** at its comma pause (so did 3 s ×1 and 3 s ×2). Final default: stream + VAD 3 s ×3, long question complete, in-ear 2258. Also fixed: the LLM request now starts in parallel with the TTS socket. | ✅ [measured] |
| 16:31 | **Object placement + split screen**: two stacked viewports (CAM_Face top, CAM_Workspace with a table, box and plate below; layout set once via viewport toolbar → TWO PANES, cameras piloted by `workspace.split_screen()`). Typed turns: "red ball on the box" → `[[place red sphere on box]]`; "green cylinder left of the box and a yellow cone behind it" → two tags, both correct; "move the red ball onto the plate" → moved the existing sphere; "clear the table" → `[[clear]]`. Action in the editor 157–256 ms, dispatched ~0.5 s after the end of the turn, so the object appears before her voice. First try took 8–14 s per action: the job subprocess inherited stdin, and on Windows that blocks while text mode's `input()` reads it (fixed: `stdin=DEVNULL`). One run stalled once waiting for the audio queue to drain after a reply (not reproduced). [measured] |
| 16:38 | "Why is the avatar frozen?": the animation was running (head bone moved, ~110 engine fps), but the top pane had **Realtime Viewport** off after the layout change, so it never redrew (0 changed pixels in 3 s; the table pane redrew). Ticked it in the pane's gauge menu: 59k pixels changed per 3 s. `editor_set_viewport_realtime(True)` doesn't help: it only removes the subsystem's own override (ensure "No realtime override was found"). [measured] |
| 16:40 | "The hair is flickering": with two panes the MetaHuman LOD alternated between 0 (top pane, close) and 2 (table pane, far) from frame to frame, so the hair swapped strands and cards. Pinned `LODSyncComponent.forced_lod = 0` (done by `workspace.split_screen()` at every bridge start); 6/6 samples LOD 0, hair renders as clean strands. [measured] |
| 16:48 | "Lip sync does not work anymore": the bridge was fine, but `jawOpen` was frozen at -0.042 for whole clips (`lipsync_latency.py`: std 0.000, editor at 89 fps). Not the LOD pin (same with it removed); nothing in the editor log; cable volumes 100 %. Re-applying the Live Link preset (`LLP_MH_Audio.apply_to_client()`) restarted the audio source: jaw moving again. The bridge now does this at every start (`--preset`), waits 3 s, then sets lookahead and captures the neutral frame. A neutral frame taken 1 s after the restart left a third of the jaw range (max 0.037); after 3 s: rest ~0, max 0.20 on `ask_story.wav`. Root cause of the freeze unknown. [measured] |
| 17:05 | "Plays but totally off from the speech": cable loopback exact (rms 0.1124 → 0.1126, digital silence when idle), jaw still in silence, so the source is on the cable. Audio → jaw now **620–700 ms** (xcorr 645–690 ms, no drift over 3 plays) vs 505 ms this morning, while the headset delay was still 0.50 s: voice ~150 ms ahead of the lips. Same after an editor restart (level saved first), so the re-applied preset wasn't the cause; preset re-apply at bridge start is now opt-in (`--restart-audio`). Default `--monitor-delay` 0.50 → 0.65 s. `lipsync_latency.py` lag search widened 0.8 → 3 s (`--max-lag`). Python can't create the audio subject from a PyJobs job (`create_audio_subject` fails even with zero timeouts). [measured] |
| 17:05 | **Hair shadow aliasing**: on 4x zooms of the face pane (100 % screen percentage, 941x389, TSR) the hair's shadow on the cheek had ~0.3 cm stair steps (= `r.HairStrands.Voxelization.Virtual.VoxelWorldSize` 0.3) and the jaw silhouette a dotted bright/dark line. Fix: voxels 0.1 cm and `r.HairStrands.DeepShadow.SuperSampling 1` (project `DefaultEngine.ini` [SystemSettings] and `workspace.render_fixes()`), sun `cast_deep_shadow` on and `light_source_angle` 0.74 → 1.0 (saved in the level), peach-fuzz groom hidden (it caused the dotted outline). Result: smooth shadow edge, clean outline. [measured] |
| 17:12 | "Still jagged, Lumen?": Lumen is off (`r.DynamicGlobalIlluminationMethod` 0, reflections SSR). Geometry edges were anti-aliased (TSR), but **shadow edges** were saw-toothed (box on the table, hair on the face): virtual shadow maps pick page resolution from the small panes. `r.Shadow.Virtual.ResolutionLodBiasDirectional -1.5`: edges straight on 3x zooms; ~85-100 fps (was ~110). In DefaultEngine.ini [SystemSettings], create_project.sh and `workspace.render_fixes()`. (`r.PostProcessAAQuality` reads 0 only because it no longer exists in 5.8.) [measured] |

## Acceptance criteria

| # | Criterion | Mac | Windows |
|---|---|---|---|
| 1 | UE 5.8 launches | ✅ | ✅ |
| 2 | Default MetaHuman renders | ❌ blocked (16 GB) | ✅ rigged (joints + blend shapes), textured, assembled (UE Cine) |
| 3 | External audio reaches Audio Live Link | 🟡 BlackHole visible to the API | ✅ CABLE Output → `MH_Audio` |
| 4 | MetaHuman visibly speaks | ⏳ | ✅ curves + captures |
| 5 | Three consecutive clips work | ⏳ | ✅ (5 runs, no freezes) |
| 6 | Results and blockers documented | ✅ | ✅ |
| + | Mood switching | ⏳ | ✅ via Python API |

## Measurements (Windows PC, 2026-10-10)

- **Audio config:** clips/bridge → "CABLE Input (VB-Audio Virtual Cable)" **WASAPI shared** 48 kHz → Live Link MetaHuman (Audio) on CABLE Output, "IEEE Float 2 ch @ 48000 Hz", lookahead 80 ms. [measured]
- **Editor FPS** (editor viewport, Epic quality, 1286×726 window, RTX 3080 Ti): 77–81 median while speaking, p99 frame 16 ms, no hitches > 100 ms in ~10 000 frames. [measured, `lipsync_latency.py`]
- **Lag, audio handed to the device → jaw curve:** 255–270 ms with WASAPI, 465 ms with MME. Rendering/display adds about 1–2 frames (~25 ms at 80 FPS) [estimate]. Screen-recording frame counting not done.
- **Voice MVP turn latency** (end of your speech → reply text): 3.3 s with `gemini-flash-latest` (= gemini-3.8-flash, always thinks ~300 tokens), **1.3 s with `gemini-flash-lite-latest` + `thinkingLevel=minimal`**; TTS first audio +95 ms after the text (socket pre-opened); +270 ms to the mouth. [measured]
- **Memory:** editor peak 16.9 GB during assembly; system commit peaked at 35.9 GB of 38.8 GB. [measured]
- **Stability:** one crash (PyJobs re-entrancy, fixed); no crashes during ~6 lip-sync runs and 3 voice turns.
