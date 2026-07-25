#!/usr/bin/env python3
"""Reference audio → UDP music streamer for the duoco_stripx HA integration.

Captures audio, computes a smoothed amplitude per 100 ms window, and sends
tiny UDP packets to Home Assistant, which forwards them to the lamp over its
existing BLE connection (arm the lamp's "Music streaming" switch first).

UDP packet format (see the HA integration's stream.py):
  [0x41, amp]        amplitude 0-100 — HA scales the current color
  [0x44, R, G, B]    direct color frame — sent as-is

Usage:
  pip install sounddevice numpy
  python music_streamer.py --host <ha-ip> [--port 8737]
      [--device <index-or-name>] [--color RRGGBB | --cycle] [--gain 2.0]
  python music_streamer.py --list-devices

Capturing *system* audio (not the mic) needs a loopback input device:
  macOS : install BlackHole (https://existential.audio/blackhole/), create a
          Multi-Output Device (speakers + BlackHole) in Audio MIDI Setup,
          then --device BlackHole
  Linux : PipeWire/Pulse expose "monitor" sources; --device 'Monitor of ...'
Any other stack (Snapcast hook, DAW send, ESP32 + mic) can implement the same
packet format trivially.
"""
from __future__ import annotations

import argparse
import socket
import sys
import time

import numpy as np
import sounddevice as sd

# App-equivalent 7-color music palette (R, G, B, Y, M, C, W)
PALETTE = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
    (255, 0, 255), (0, 255, 255), (255, 255, 255),
]

FRAME_INTERVAL = 0.1  # 10 Hz, same cadence as the app's send timer


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", help="Home Assistant IP/hostname")
    ap.add_argument("--port", type=int, default=8737)
    ap.add_argument("--device", help="capture device index or name substring")
    ap.add_argument("--color", metavar="RRGGBB",
                    help="fixed base color; sends direct color packets")
    ap.add_argument("--cycle", action="store_true",
                    help="cycle the app's 7-color palette (direct color packets)")
    ap.add_argument("--gain", type=float, default=3.0,
                    help="amplitude gain (default 3.0)")
    ap.add_argument("--list-devices", action="store_true")
    args = ap.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return
    if not args.host:
        ap.error("--host is required (or use --list-devices)")

    base_color = None
    if args.color:
        v = int(args.color, 16)
        base_color = ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (args.host, args.port)

    samplerate = 44100
    blocks: list[np.ndarray] = []

    def on_audio(indata, _frames, _time, status) -> None:
        if status:
            print(status, file=sys.stderr)
        blocks.append(indata.copy())

    # Attack fast / decay slow so beats hit hard and fades look smooth.
    level = 0.0
    palette_i = 0
    device = args.device
    if device is not None and device.isdigit():
        device = int(device)

    with sd.InputStream(device=device, channels=1, samplerate=samplerate,
                        callback=on_audio):
        info = sd.query_devices(device, "input") if device is not None else \
            sd.query_devices(kind="input")
        print(f"capturing from: {info['name']}  →  udp://{dest[0]}:{dest[1]}")
        print("Ctrl-C to stop (HA's watchdog restores the lamp ~5 s later)")
        try:
            while True:
                time.sleep(FRAME_INTERVAL)
                if blocks:
                    samples = np.concatenate(blocks)
                    blocks.clear()
                    rms = float(np.sqrt(np.mean(samples**2)))
                else:
                    rms = 0.0
                target = min(1.0, rms * args.gain)
                level = max(target, level * 0.7)  # instant attack, ~0.7 decay
                amp = round(level * 100)

                if base_color or args.cycle:
                    color = base_color or PALETTE[palette_i]
                    palette_i = (palette_i + 1) % len(PALETTE)
                    r, g, b = (round(c * amp / 100) for c in color)
                    sock.sendto(bytes([0x44, r, g, b]), dest)
                else:
                    sock.sendto(bytes([0x41, amp]), dest)
        except KeyboardInterrupt:
            print("\nstopped.")


if __name__ == "__main__":
    main()
