"""Record MetaHuman face-control curves every editor frame, without blocking the game thread.

  import record_curves; record_curves.start(seconds=30)   # returns the CSV path immediately

A Slate post-tick callback appends one row per frame:
  perf_counter, dt, face LOD, <CURVES on the Body's Live Link anim instance>, face rig outputs
and writes <Project>/Saved/curve_log.csv when the time is up. time.perf_counter() is the
system-wide QueryPerformanceCounter on Windows, so rows line up with timestamps taken in
other processes (scripts/lipsync_latency.py). UE's time.time() only ticks every 15.6 ms.
"""
import csv
import os
import time

import unreal

CURVES = ["CTRL_expressions_jawOpen", "CTRL_expressions_mouthFunnelUL", "CTRL_expressions_mouthLipsTogetherUL",
          "CTRL_expressions_mouthCornerPullL"]
FACE_CURVE = "head_lod0_mesh__jaw_open"
_state = {}


def _actor(label):
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return next(a for a in eas.get_all_level_actors() if a.get_actor_label() == label)


def _tick(dt):
    s = _state
    now = time.perf_counter()
    s["rows"].append([now, dt, s["face_comp"].get_predicted_lod_level()]
                     + [s["body"].get_curve_value(c) for c in s["curves"]]
                     + [s["face"].get_curve_value(c) for c in s["face_curves"]])
    if now >= s["end"]:
        unreal.unregister_slate_post_tick_callback(s["handle"])
        with open(s["path"], "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["perf", "dt", "face_lod"] + s["curves"] + ["face:" + c for c in s["face_curves"]])
            w.writerows(s["rows"])
        unreal.log(f"[record_curves] {len(s['rows'])} frames -> {s['path']}")
        s.clear()


def start(seconds=30.0, label="MH_Avatar", all_curves=False):
    """all_curves=True logs every CTRL_expressions_* solver output and the face's mouth/jaw rig outputs."""
    if _state:
        raise RuntimeError("a recording is already running")
    a = _actor(label)
    path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "curve_log.csv")
    if os.path.exists(path):
        os.remove(path)
    body = a.get_editor_property("Body").get_anim_instance()
    face_comp = a.get_editor_property("Face")
    face = face_comp.get_anim_instance()
    curves, face_curves = list(CURVES), [FACE_CURVE]
    if all_curves:
        curves = sorted(str(c) for c in body.get_all_curve_names() if str(c).startswith("CTRL_expressions_"))
        face_curves = sorted(str(c) for c in face.get_all_curve_names()
                             if (str(c).startswith("head_lod0_mesh__") and any(k in str(c).lower() for k in ("mouth", "lip", "jaw", "blink")))
                             or str(c) in ("CTRL_expressions_eyeBlinkL", "CTRL_expressions_eyeBlinkR"))
    _state.update(rows=[], path=path, end=time.perf_counter() + seconds, body=body, face=face, face_comp=face_comp,
                  curves=curves, face_curves=face_curves)
    _state["handle"] = unreal.register_slate_post_tick_callback(_tick)
    return path
