"""Create a MetaHuman (Audio) Live Link source + subject and control mood, from Unreal Python.

Every call here maps to a BlueprintCallable UFUNCTION verified in the installed UE 5.8.3 headers:
  UMetaHumanLocalLiveLinkSourceBlueprint (MetaHumanLocalLiveLinkSourceBlueprint.h):
    GetAudioDevices, GetAudioTracks, GetAudioFormats, CreateAudioSource, CreateAudioSubject, GetSubjectSettings
  UMetaHumanAudioBaseLiveLinkSubjectSettings (MetaHumanAudioBaseLiveLinkSubjectSettings.h):
    SetMood / GetMood, SetMoodIntensity / GetMoodIntensity (0..1), SetLookahead / GetLookahead (80..240)
  EAudioDrivenAnimationMood (SpeechAnimationSolverTypes.h):
    AUTO_DETECT, NEUTRAL, HAPPINESS, SADNESS, DISGUST, ANGER, SURPRISE, FEAR,
    CONFIDENCE, EXCITEMENT, BOREDOM, PLAYFULNESS, CONFUSION

Python binding note: UE turns C++ out-params into return values (a single value, or a tuple
in declaration order). Run `introspect_metahuman_api.py` once to confirm the exact Python shapes.

Usage in the editor Python console:
  import mh_audio_livelink as m
  m.list_devices()
  key = m.connect("BlackHole 2ch", "MH_Audio_BH")
  m.set_mood(key, "HAPPINESS", 0.8)
"""
import unreal

BP = unreal.MetaHumanLocalLiveLinkSourceBlueprint
_last_subject = None


def _as_list(result):
    return list(result[0] if isinstance(result, tuple) else result)


def list_devices():
    devices = _as_list(BP.get_audio_devices(True))
    for i, d in enumerate(devices):
        unreal.log(f"[{i}] {d.get_editor_property('name')}")
    return devices


def connect(device_substring="BlackHole", subject_name="MH_Audio_BH", sample_rate=48000):
    """Create an audio source and a subject on the first device whose name contains device_substring.

    Formats are listed highest-rate first (BlackHole offers 768 kHz down to 8 kHz); CreateAudioSubject
    fails on the 768 kHz entry, so pick by sample rate (48 kHz = BlackHole default = bridge contract).
    """
    global _last_subject
    devices = [d for d in _as_list(BP.get_audio_devices(True))
               if device_substring.lower() in str(d.get_editor_property("name")).lower()]
    if not devices:
        raise RuntimeError(f"No audio device matching {device_substring!r}; see list_devices()")
    device = devices[0]

    tracks, timed_out = BP.get_audio_tracks(device, 5.0)
    if timed_out or not tracks:
        raise RuntimeError(f"No audio tracks on {device.get_editor_property('name')} (timed_out={timed_out})")
    formats, timed_out = BP.get_audio_formats(tracks[0], 5.0)
    if timed_out or not formats:
        raise RuntimeError(f"No audio formats (timed_out={timed_out})")
    fmt = next((f for f in formats if f.sample_rate == sample_rate), None)
    if fmt is None:
        raise RuntimeError(f"No {sample_rate} Hz format; available: {[f.sample_rate for f in formats]}")

    source, ok = BP.create_audio_source()
    if not ok:
        raise RuntimeError("CreateAudioSource failed")
    subject, ok = BP.create_audio_subject(source, fmt, subject_name)
    if not ok:
        raise RuntimeError("CreateAudioSubject failed")
    unreal.log(f"Connected {device.get_editor_property('name')} -> subject {subject_name}")
    _last_subject = subject
    return subject


def settings(subject=None):
    s = BP.get_subject_settings(subject or _last_subject)
    if not isinstance(s, unreal.MetaHumanAudioBaseLiveLinkSubjectSettings):
        raise RuntimeError(f"Subject settings are {type(s).__name__}, not audio settings")
    return s


def set_mood(subject=None, mood="NEUTRAL", intensity=1.0):
    s = settings(subject)
    s.set_mood(getattr(unreal.AudioDrivenAnimationMood, mood.upper()))
    s.set_mood_intensity(float(intensity))
    unreal.log(f"mood={s.get_mood()} intensity={s.get_mood_intensity()}")


def set_lookahead(subject=None, ms=80):
    s = settings(subject)
    s.set_lookahead(int(ms))
    unreal.log(f"lookahead={s.get_lookahead()} ms")
