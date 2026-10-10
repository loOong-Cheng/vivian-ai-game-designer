#!/usr/bin/env python3
"""Play one or more WAV files to a named output device (BlackHole 2ch on macOS, CABLE Input on Windows).

Usage:
  .venv/bin/python scripts/play_to_device.py --list
  .venv/bin/python scripts/play_to_device.py --device "BlackHole 2ch" test_audio/clip*.wav --gap 1.0
  .venv/Scripts/python scripts/play_to_device.py test_audio/clip1.wav   # Windows: defaults to "CABLE Input"

Each clip is resampled-free: the device is opened at the file's sample rate, so
generate clips at 48 kHz (BlackHole default) to avoid CoreAudio rate conversion.
Mono files are duplicated to every output channel.
"""
import argparse
import sys
import time

import numpy as np
import sounddevice as sd
import soundfile as sf


def find_output(name: str, hostapi: str = "") -> int:
    matches = [i for i, d in enumerate(sd.query_devices())
               if name.lower() in d["name"].lower() and d["max_output_channels"] > 0
               and hostapi.lower() in sd.query_hostapis(d["hostapi"])["name"].lower()]
    if not matches:
        sys.exit(f"No output device matching {name!r}. Run with --list.")
    return matches[0]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("files", nargs="*")
    p.add_argument("--device", default="CABLE Input" if sys.platform == "win32" else "BlackHole 2ch")
    p.add_argument("--hostapi", default="WASAPI" if sys.platform == "win32" else "",
                   help="host API filter; on Windows WASAPI cut audio->mouth lag from 465 to 270 ms vs MME")
    p.add_argument("--gap", type=float, default=1.0, help="seconds of silence between clips")
    p.add_argument("--list", action="store_true")
    a = p.parse_args()

    if a.list:
        print(sd.query_devices())
        return
    if not a.files:
        p.error("no files given")

    dev = find_output(a.device, a.hostapi)
    info = sd.query_devices(dev)
    ch = min(2, info["max_output_channels"])
    print(f"device [{dev}] {info['name']} ({sd.query_hostapis(info['hostapi'])['name']}, "
          f"default rate {info['default_samplerate']:.0f} Hz)")

    for i, path in enumerate(a.files):
        data, rate = sf.read(path, dtype="float32", always_2d=True)
        if data.shape[1] < ch:
            data = np.repeat(data[:, :1], ch, axis=1)
        dur = len(data) / rate
        t0 = time.monotonic()
        print(f"[{i + 1}/{len(a.files)}] {path}: {dur:.2f}s @ {rate} Hz  start={time.strftime('%H:%M:%S')}")
        sd.play(data[:, :ch], rate, device=dev, blocking=True)
        print(f"      done in {time.monotonic() - t0:.2f}s")
        if i < len(a.files) - 1:
            time.sleep(a.gap)


if __name__ == "__main__":
    main()
