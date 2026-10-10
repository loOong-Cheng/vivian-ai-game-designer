#!/usr/bin/env python3
"""Stream microphone (or a WAV) as raw 48 kHz int16 mono PCM over UDP to audio_recv.py.

Runs on the Mac on site; audio_recv.py on the Windows PC plays it into "CABLE Input",
which the MetaHuman (Audio) Live Link source listens to via "CABLE Output".

  .venv/bin/python scripts/audio_send.py --host 192.168.1.50            # default mic
  .venv/bin/python scripts/audio_send.py --host 192.168.1.50 --device "MacBook Air Microphone"
  .venv/bin/python scripts/audio_send.py --host 192.168.1.50 --wav test_audio/clip1.wav
  .venv/bin/python scripts/audio_send.py --list

Packet = 6-byte header (uint32 seq, uint16 n_samples, big-endian) + n_samples int16 LE.
10 ms frames (480 samples, 966 bytes) stay below any VPN MTU.
"""
import argparse
import socket
import struct
import sys
import time

import numpy as np
import sounddevice as sd

RATE = 48000
FRAME = 480  # 10 ms
HDR = struct.Struct("!IH")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", help="IP of the PC running audio_recv.py")
    p.add_argument("--port", type=int, default=50555)
    p.add_argument("--device", help="input device name (substring) or index; default = system mic")
    p.add_argument("--wav", help="stream this WAV (48 kHz) in real time instead of the mic")
    p.add_argument("--list", action="store_true", help="list audio devices and exit")
    a = p.parse_args()

    if a.list:
        print(sd.query_devices())
        return
    if not a.host:
        p.error("--host is required")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (a.host, a.port)
    seq = 0

    def send(block):
        nonlocal seq
        pcm = np.clip(block * 32767.0, -32768, 32767).astype("<i2")
        sock.sendto(HDR.pack(seq & 0xFFFFFFFF, len(pcm)) + pcm.tobytes(), dest)
        seq += 1

    if a.wav:
        import soundfile as sf
        data, sr = sf.read(a.wav, dtype="float32", always_2d=True)
        if sr != RATE:
            sys.exit(f"{a.wav} is {sr} Hz; need {RATE}")
        mono = data.mean(axis=1)
        print(f"Streaming {a.wav} ({len(mono) / RATE:.2f} s) to {dest}")
        t0 = time.perf_counter()
        for i, start in enumerate(range(0, len(mono), FRAME)):
            send(mono[start:start + FRAME])
            delay = t0 + (i + 1) * FRAME / RATE - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
        return

    device = int(a.device) if a.device and a.device.isdigit() else a.device

    def callback(indata, frames, t, status):
        if status:
            print(status, file=sys.stderr)
        send(indata[:, 0])

    with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=FRAME,
                        device=device, callback=callback, latency="low"):
        name = sd.query_devices(device if device is not None else sd.default.device[0])["name"]
        print(f"Streaming mic '{name}' -> {dest} (48 kHz mono, 10 ms frames). Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
