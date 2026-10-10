#!/usr/bin/env python3
"""Receive audio_send.py's UDP PCM stream and play it into a virtual cable.

Runs on the Windows PC (needs Python + sounddevice). Plays continuously and outputs
silence when nothing arrives, so the Live Link stream never closes (bridge contract).

  .venv\\Scripts\\python scripts\\audio_recv.py                       # -> "CABLE Input"
  .venv\\Scripts\\python scripts\\audio_recv.py --device "Speakers"   # monitor locally
  .venv\\Scripts\\python scripts\\audio_recv.py --list

Jitter buffer: playback starts once --prefill ms are queued; if the queue grows past
--max-buffer ms (VPN burst), the oldest frames are dropped so latency stays bounded.
Stats line every 5 s: received/lost/late packets, underruns, current buffer depth.
"""
import argparse
import collections
import socket
import struct
import sys
import threading
import time

import numpy as np
import sounddevice as sd

RATE = 48000
FRAME = 480  # 10 ms, must match audio_send.py
HDR = struct.Struct("!IH")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=50555)
    p.add_argument("--device", default="CABLE Input", help="output device name (substring) or index")
    p.add_argument("--prefill", type=int, default=40, help="ms queued before playback (re)starts")
    p.add_argument("--max-buffer", type=int, default=150, help="ms; drop oldest above this")
    p.add_argument("--list", action="store_true")
    a = p.parse_args()

    if a.list:
        print(sd.query_devices())
        return

    prefill = max(1, a.prefill // 10)
    max_frames = max(prefill + 1, a.max_buffer // 10)
    q = collections.deque()
    lock = threading.Lock()
    st = dict(rx=0, lost=0, late=0, dropped=0, underruns=0, next_seq=None, playing=False)

    def receiver():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
        sock.bind(("0.0.0.0", a.port))
        while True:
            pkt, _ = sock.recvfrom(4096)
            if len(pkt) < HDR.size:
                continue
            seq, n = HDR.unpack_from(pkt)
            pcm = np.frombuffer(pkt, dtype="<i2", count=n, offset=HDR.size).astype(np.float32) / 32768.0
            with lock:
                st["rx"] += 1
                exp = st["next_seq"]
                if exp is not None and seq < exp and exp - seq < 1000:
                    st["late"] += 1  # reordered/late: discard
                    continue
                if exp is not None and seq > exp:
                    st["lost"] += seq - exp
                st["next_seq"] = seq + 1
                q.append(pcm)
                while len(q) > max_frames:
                    q.popleft()
                    st["dropped"] += 1

    def callback(outdata, frames, t, status):
        out = np.zeros(frames, dtype=np.float32)
        filled = 0
        with lock:
            if not st["playing"] and len(q) >= prefill:
                st["playing"] = True
            while st["playing"] and filled < frames:
                if not q:
                    st["playing"] = False
                    st["underruns"] += 1
                    break
                chunk = q[0]
                take = min(len(chunk), frames - filled)
                out[filled:filled + take] = chunk[:take]
                if take < len(chunk):
                    q[0] = chunk[take:]
                else:
                    q.popleft()
                filled += take
        outdata[:] = np.repeat(out[:, None], outdata.shape[1], axis=1)

    device = int(a.device) if a.device.isdigit() else a.device
    threading.Thread(target=receiver, daemon=True).start()
    with sd.OutputStream(samplerate=RATE, channels=2, dtype="float32", blocksize=FRAME,
                         device=device, callback=callback, latency="low") as stream:
        name = sd.query_devices(stream.device)["name"]
        print(f"Listening UDP :{a.port} -> '{name}' 48 kHz stereo, "
              f"output latency {stream.latency * 1000:.0f} ms, prefill {prefill * 10} ms. Ctrl+C to stop.")
        try:
            while True:
                time.sleep(5)
                with lock:
                    print(f"rx={st['rx']} lost={st['lost']} late={st['late']} dropped={st['dropped']} "
                          f"underruns={st['underruns']} buffer={len(q) * 10} ms", file=sys.stderr)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
