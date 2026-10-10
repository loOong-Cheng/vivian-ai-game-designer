# MetaHuman setup (default MetaHuman, animation-ready)

**Status:** pending engine install. Anything marked _(verify)_ comes from earlier UE versions and must be confirmed against the installed 5.8 editor before this doc is finalized. Don't copy those labels as fact.

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
