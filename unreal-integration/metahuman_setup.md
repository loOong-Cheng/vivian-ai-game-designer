# MetaHuman setup (default MetaHuman, animation-ready)

**Status:** ✅ verified on Windows, UE 5.8.3, 2026-10-10. See "Verified route (Windows)" just below. The older route further down is kept for reference; anything still marked _(verify)_ there is unconfirmed.

## Verified route (Windows, UE 5.8.3)

| Step | How (all scriptable) | Result |
|---|---|---|
| Create | MCP `metahuman_toolset.metahuman.MetaHumanToolset.create {"asset_path": "/Game/MH/MHC_Default"}` | `MetaHumanCharacter` asset |
| Open | MCP `EditorToolset.EditorAppToolset.OpenEditorForAsset` | MetaHuman Creator; "Missing Project Settings" → Enable Missing (3 renderer settings, restart) |
| Rig | Toolbar **Create Full Rig** (Joints and Blend Shapes), or `request_auto_rigging` | Epic cloud; browser login the first time; 50.7 s |
| Textures | `MetaHumanCharacterEditorSubsystem.request_texture_sources(ch, MetaHumanCharacterTextureRequestParams(report_progress=True))` | 2k face + body in ~10 s |
| Assemble | `build_meta_human(ch, MetaHumanCharacterEditorBuildParameters(pipeline_type=CINEMATIC))` with the asset open in the editor, then `EditorLoadingAndSavingUtils.save_dirty_packages(False, True)` | `/Game/MH/Unpacked/MHC_Default/BP_MHC_Default` + 49 packages; 65 s on SM6 |
| Place | `EditorActorSubsystem.spawn_actor_from_class(bp.generated_class(), (0,0,0))`, label `MH_Default` | Face looks along +Y; nose tip ≈ z 157 cm |
| Bind | Actor properties `UseLiveLink=True`, `UseARKit=False`, `LiveLinkSubject=LiveLinkSubjectName(name="MH_Audio")` | Body anim class → `LiveLinkInstance`; Face `ABP_Face` reads the curves; updates in the editor viewport |

**Idle head/body motion:** `BP_MHC_Vivian`'s construction script assigns the Body `/Game/MH/ABP_Body_IdleLiveLink` (Play `AS_MH_Neutral_Stand_Idle_Loop` → Live Link Pose `MH_Audio` → Output) instead of `LiveLinkInstance`. The face copies head and neck from the body, so the head sways ≤ 3.6°. `LiveLinkSetup`'s cast to `LiveLinkInstance` now fails harmlessly, since the subject is set on the node. **Re-assembling the MetaHuman regenerates the BP and undoes this.** Re-point `K2Node_CallFunction_0.NewClass` in `UserConstructionScript`.

**Looking at the camera** (same body AnimBP): Local→Component → Transform (Modify) Bone `head` (**Replace, World space**, Rotation ← `LookRot`, Alpha ← `LookAlpha`) → nods → Component→Local. The EventGraph computes `LookRot = MakeRotFromYX(CamTarget − head, up)` (head bone +Y = face forward, +X = up) and a smoothstep `LookAlpha` schedule (every 4–9 s, hold 1.5–3.5 s), skipped while `CamTarget` is zero. The bridge sets the instance-editable `CamTarget` from `CAM_Face`, lowered by distance·tan 3.8° because the eyes rest 3.8° above the head axis. Don't use the engine Look At node here: it stopped the whole graph evaluating.

**Mood loops and talking nods** (same body AnimBP; the bridge leaves `BodyMood` at 0 unless run with `--body-moods`): idle → three chained Blend Poses by int (happy_f / sad_f / surprise_m body loops from `/MetaHumanCharacter/Optional/Animation/TemplateAnimations/Expression_Loops`, 0.6 s blends, selectors computed from the instance-editable int `BodyMood`) → Live Link Pose → Transform (Modify) Bone on `head` driven by `HeadOffset`, which the EventGraph computes from the lip-sync jaw curve. Set `BodyMood` from Python with `body_anim_instance.set_editor_property('BodyMood', n)`. The bridge does this per reply.

**Blinking:** the face graph is Copy Pose From Mesh → Modify Curve (Scale × 0 on eyeBlinkL/R, which mutes the solver's blinks; they flutter after a while) → Modify Curve (Blend → 1.0, Alpha ← `BlinkAlpha`) → Output.

**Idle blinking** (the audio solver doesn't blink in silence): `MH_Avatar`'s Face uses `/Game/MH/ABP_Face_Blink` instead of `/MetaHumanCharacter/Face/ABP_Face`. It's a copy whose AnimGraph is Copy Pose From Mesh → Modify Curve (eyeBlinkL/R → 1.0, Blend, Alpha ← `BlinkAlpha`) → Output, with an EventGraph that fires a 160 ms blink every 2–5 s. Built entirely with MCP `BlueprintTools` (`create_node`, `connect_pins`, `add_variable`, `write_graph_dsl`) plus Python for the node's `curve_map`/`apply_mode`. After re-assembling or re-placing a MetaHuman, set the Face component's `anim_class` to `ABP_Face_Blink_C` again.

How the binding works (read with MCP `BlueprintTools.read_graph_dsl`): `OnAnimInitialized(Face/Body)` calls `LiveLinkSetup(Body, LiveLinkSubject, …, UseLiveLink)`, which calls `LiveLink|SetSubject` on the body's `LiveLinkInstance` (ARKit mode instead uses `ABP_MH_LiveLink` and `LLink_Face_Subj`). The construction script picks the anim class. Requirements: **SM6** (see `WINDOWS_HANDOFF.md`) and the three GPUSkin/SkinCache settings.

## Route: create in-editor with MetaHuman Creator (UE 5.7+, works on Mac)

1. Open `GradiumMH.uproject`.
2. In the **Content Browser**, create a folder `/Game/MH`.
3. Right-click → **MetaHuman → MetaHuman Character** _(verify menu path)_ and name it `MHC_Default`.
4. Open it and pick a **preset** (no scanning or identity work, per the milestone scope).
5. **Assemble** _(verify button name)_ with an assembly pipeline that produces an **animation-ready** Blueprint actor, not an "optimized/baked" one. It needs the face rig (RigLogic + DNA) intact for Live Link curves.
6. Drag the resulting Blueprint into the level `L_AudioTest`.

Fallback if Creator fails on macOS 26 or 16 GB RAM: download a preset MetaHuman through **Fab** (Window → Fab) into the project.

## Test level

- **File → New Level → Basic** and save as `/Game/Maps/L_AudioTest`.
- Put a CineCamera about 60 cm in front of the face, with focus tracking on the head.
- Lighting: the default directional + sky light is fine. Turn off Lumen hardware ray tracing (Project Settings → Rendering) to save memory and GPU.

## Binding the Audio Live Link subject

Epic's audio-source page stops at "the subject is ready to animate a MetaHuman". The binding has to be confirmed in the installed editor.

1. Select the MetaHuman actor in the level.
2. In **Details**, find the Live Link section _(verify; earlier versions had `LLink Face Subj` and `LLink Face Act` on the MetaHuman BP)_.
3. Set the face subject to `MH_Audio_Mic` / `MH_Audio_BH`, and enable face Live Link.
4. In-editor preview: Live Link animates the actor in the editor viewport when **Update Animation in Editor** is on for the face skeletal mesh _(verify)_; otherwise press **Simulate/PIE**.

## Render check

- [ ] The character appears with hair, eyes and teeth (not grey or default materials).
- [ ] No pink or missing shaders after shader compilation finishes.
- [ ] The viewport FPS counter shows a stable rate (Viewport ▾ → Show FPS).

The exact verified steps and screenshots will replace this section after the run.
