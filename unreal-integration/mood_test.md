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

## Results

_pending_
