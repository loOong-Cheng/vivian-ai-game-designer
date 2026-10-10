#!/usr/bin/env python3
"""Measure audio -> MetaHuman mouth lag, FPS and continuity at the animation-curve level.

  .venv/Scripts/python scripts/lipsync_latency.py test_audio/clip1.wav test_audio/clip2.wav test_audio/clip3.wav

Starts scripts/ue/record_curves.py in the running editor (via ue_exec.py / PyJobs), plays the
clips into the loopback device with perf_counter timestamps, then cross-correlates the
CTRL_expressions_jawOpen curve with each clip's RMS envelope. The lag covers everything from
"the bridge hands audio to the device" to "the face rig input moves": device buffering, the
virtual cable, Unreal's audio capture, the Live Link solver and its lookahead. Rendering and
display add roughly one or two frames on top. Uses perf_counter, which is system-wide on Windows.
"""
import argparse
import csv
import os
import subprocess
import sys
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
HOP = 0.005


def ue(code, timeout=60):
    r = subprocess.run([sys.executable, os.path.join(HERE, "ue_exec.py"), "--timeout", str(timeout), "-c", code],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ue_exec failed:\n{r.stdout}{r.stderr}")
    return r.stdout.strip()


def envelope(data, rate):
    n = int(rate * HOP)
    frames = data[: len(data) // n * n, 0].reshape(-1, n)
    return np.sqrt((frames ** 2).mean(axis=1))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("files", nargs="+")
    p.add_argument("--device", default="CABLE Input" if sys.platform == "win32" else "BlackHole 2ch")
    p.add_argument("--hostapi", default="", help='e.g. "WASAPI" (Windows: the first match is otherwise MME)')
    p.add_argument("--gap", type=float, default=1.5)
    p.add_argument("--lead", type=float, default=2.0, help="silence recorded before the first clip")
    p.add_argument("--max-lag", type=float, default=3.0, help="longest lag searched (s)")
    p.add_argument("--tail", type=float, default=2.0)
    p.add_argument("--label", default="MH_Avatar", help="actor label of the MetaHuman")
    a = p.parse_args()

    clips = [sf.read(f, dtype="float32", always_2d=True) for f in a.files]
    dev = next(i for i, d in enumerate(sd.query_devices())
               if a.device.lower() in d["name"].lower() and d["max_output_channels"] > 0
               and a.hostapi.lower() in sd.query_hostapis(d["hostapi"])["name"].lower())
    print(f"output: [{dev}] {sd.query_devices(dev)['name']} ({sd.query_hostapis(sd.query_devices(dev)['hostapi'])['name']})")
    total = a.lead + sum(len(d) / r for d, r in clips) + a.gap * (len(clips) - 1) + a.tail + 1.0

    path = ue("import importlib, record_curves; importlib.reload(record_curves); "
              f"print(record_curves.start({total:.1f}, {a.label!r}))")
    print(f"recording {total:.1f}s -> {path}")
    time.sleep(a.lead)
    starts = []
    for i, ((data, rate), f) in enumerate(zip(clips, a.files)):
        starts.append(time.perf_counter())
        sd.play(np.repeat(data[:, :1], 2, axis=1), rate, device=dev, blocking=True)
        print(f"played {f} ({len(data) / rate:.2f}s)")
        if i < len(clips) - 1:
            time.sleep(a.gap)
    while not os.path.exists(path):
        time.sleep(0.2)
    time.sleep(0.3)

    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    head, body = rows[0], np.array(rows[1:], dtype=float)
    t, dt, jaw = body[:, 0], body[:, 1], body[:, head.index("CTRL_expressions_jawOpen")]

    # Session-wide audio envelope on a HOP grid, zero outside the clips.
    grid = np.arange(t[0] - 1.0, t[-1] + 1.0, HOP)
    env = np.zeros_like(grid)
    windows = []
    for (data, rate), s in zip(clips, starts):
        e = envelope(data, rate)
        k = int(round((s - grid[0]) / HOP))
        env[k:k + len(e)] = e[: max(0, len(env) - k)]
        windows.append((s, s + len(data) / rate))

    lags = np.arange(0.0, a.max_lag, HOP)
    jc = jaw - jaw.mean()
    corr = [np.corrcoef(jc, np.interp(t - L, grid, env))[0, 1] for L in lags]
    best = lags[int(np.argmax(corr))]

    speech = np.zeros(len(t), bool)
    for s, e in windows:
        speech |= (t >= s + best) & (t <= e + best)
    silence = np.ones(len(t), bool)
    for s, e in windows:
        silence &= (t < s + best - 0.3) | (t > e + best + 0.5)

    runs, run = [], 1
    for i in range(1, len(jaw)):
        if speech[i] and jaw[i] == jaw[i - 1]:
            run += 1
        else:
            runs.append(run)
            run = 1
    runs.append(run)

    print(f"\nframes {len(t)}  FPS median {1 / np.median(dt):.1f}  dt p99 {np.percentile(dt, 99) * 1000:.1f} ms  "
          f"max {dt.max() * 1000:.1f} ms  hitches >100 ms: {(dt > 0.1).sum()}")
    print(f"lag (xcorr jawOpen vs audio envelope): {best * 1000:.0f} ms  (r = {max(corr):.3f})")
    print(f"jawOpen silence: mean {jaw[silence].mean():.3f} max {jaw[silence].max():.3f}  |  "
          f"speech: mean {jaw[speech].mean():.3f} max {jaw[speech].max():.3f} std {jaw[speech].std():.3f}")
    print(f"longest unchanged jawOpen run during speech: {max(runs)} frames")
    base, sd_ = jaw[silence].mean(), jaw[silence].std()
    for (s, e), f in zip(windows, a.files):
        m = (t >= s) & (t <= e + best)
        on = t[m][jaw[m] > base + max(3 * sd_, 0.05)]
        onset = f"{(on[0] - s) * 1000:.0f} ms" if len(on) else "none"
        print(f"  {os.path.basename(f)}: first jaw movement {onset} after play() start, max jawOpen {jaw[m].max():.3f}")


if __name__ == "__main__":
    main()
