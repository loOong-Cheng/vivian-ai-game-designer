# Mood controls (Phase 4)

**Status:** pending, starts once lip-sync works.

## What Epic documents

From [Using a MetaHuman Audio Source](https://dev.epicgames.com/documentation/metahuman/using-a-metahuman-audio-source-in-unreal-engine): select the subject → **Controls → Mood**, then pick a mood and an intensity. Neutral has no intensity.

The documented moods are Neutral, Happy, Confident, Excited, Playful, Sad, Bored, Fear, Confused, Disgust, Anger, Surprise.

The online Python and C++ reference for `MetaHumanAudioBaseLiveLinkSubjectSettings` lists **Get Mood / Get Mood Intensity**, plus a `Mood` property (`EAudioDrivenAnimationMood`) and a `MoodIntensity` float. A **Set Mood** function wasn't visible in the reference excerpt. It has to be confirmed in the installed plugin headers and `metahuman_api_dump.txt` before anything is built on it.

## Test plan

1. Play `clip1 → clip2 → clip3` in a loop through BlackHole.
2. During clip 2, switch the mood in the subject panel: Neutral → Happy (intensity 1.0) → Sad (1.0).
3. Record the following:
   - whether the expression change is visible, and how long it takes to blend
   - whether lip motion keeps going through the switch (no freeze, pop or re-init)
   - whether intensity values in 0–1 behave linearly
4. Repeat the switch through the Blueprint path once it's verified.

## External emotion events (Blueprint component)

The plan is a small actor component `BPC_EmotionReceiver` with:

- **Input:** `ApplyEmotion(Mood: EAudioDrivenAnimationMood, Intensity: float)`
- **Action:** get the Live Link subject's settings object and set the mood and intensity, using only setter nodes and property names that the API dump shows to exist.
- **Transport (later):** a small listener the Python bridge can reach, such as a Remote Control HTTP call or a TCP/UDP plugin. The choice is deferred, and the Claude API isn't part of this phase.

## Results (Windows, 2026-10-10) [measured]

`SetMood` / `SetMoodIntensity` **do exist** and work from Python: `MetaHumanLocalLiveLinkSourceBlueprint.get_subject_settings(key)` returns `MetaHumanAudioLiveLinkSubjectSettings`. Same speech (clip1 + clip2) per mood, intensity 1.0, curves logged every frame by `scripts/ue/record_curves.py`:

| Mood | `mouthCornerPullL` mean / max | jawOpen max | Lag |
|---|---|---|---|
| Neutral | 0.012 / 0.043 | 0.559 | 260 ms |
| Happiness | **0.349 / 0.654** | 0.618 | 260 ms |
| Sadness | 0.036 / 0.107 | 0.585 | 255 ms |

Lip motion carried on under every mood (the curve changed every frame, no freezes). The mood was switched between utterances, not mid-utterance; the blend time for a mid-speech switch hasn't been measured yet. The voice bridge (`dt/bridge/avatar_chat.py`) applies a mood per reply from Gemini's tag ([happy], [sad], [excited], …) at intensity 0.8. With `[excited]` the smile curve rose to 0.10–0.28 during the reply.
