#!/usr/bin/env python3
"""Reference audio -> UDP music streamer for the duoco_stripx HA integration.

Runs three independent bandpass filters (bass/mid/treble) and an adaptive
energy-threshold beat detector on each, loosely inspired by Frederic
Patin's classic "Beat Detection Algorithms" (see link below). Kick drums
live in the bass band, snare "crack" in mid, hi-hats/cymbals in treble --
a single band can only ever see one of those. Each band has its own
weight, so you can tune how much a hit in that register should brighten
the flash. A detected beat triggers an instant-attack/slow-decay flash.
This tracks the song's actual rhythm far better than raw broadband
peak/RMS, which reacts to anything loud (vocals, sustained pads) rather
than specifically to percussive hits.

Sends tiny UDP packets to Home Assistant, which forwards them to the lamp
over its existing BLE connection (arm the lamp's "Music streaming" switch
first).

The lamp does no audio processing of its own -- HA just relays whatever RGB
this script sends. UDP packet format (see the HA integration's stream.py):
  [R, G, B]    exactly 3 bytes, forwarded to the lamp as-is

Algorithm background: Frederic Patin, "Beat Detection Algorithms"
  https://www.flipcode.com/misc/BeatDetectionAlgorithms.pdf

Usage:
  pip install sounddevice numpy scipy
  python music_streamer.py --host <ha-ip> [--port 8737]
      [--device <index-or-name>] [--color RRGGBB | --cycle]
      [--bass-low 50] [--bass-high 150] [--weight-bass 1.0]
      [--mid-low 200] [--mid-high 2000] [--weight-mid 0.5]
      [--treble-low 3000] [--treble-high 8000] [--weight-treble 0.7]
      [--sensitivity 1.3] [--gain 1.0] [--min-energy 3e-5] [--debug]
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
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd
from scipy.signal import butter, sosfilt

# App-equivalent 7-color music palette (R, G, B, Y, M, C, W)
PALETTE = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
    (255, 0, 255), (0, 255, 255), (255, 255, 255),
]

SAMPLE_RATE = 44100
BLOCK_SIZE = 1024  # ~23ms per audio callback
FRAME_INTERVAL = 0.05  # 20 Hz -- matches the HA relay's FORWARD_INTERVAL
DECAY = 0.7 ** (FRAME_INTERVAL / 0.1)  # post-beat flash decay, ~0.7 per 100ms

HISTORY_SECONDS = 1.0  # rolling window the adaptive threshold is computed over
REFRACTORY_SECONDS = 0.15  # minimum gap between beats (avoids double-triggers)


class BandDetector:
    """Bandpass-filters audio to one frequency register, then flags a beat
    whenever that band's short-term energy spikes above its own recent
    rolling average. The threshold adapts to variance in that history, so
    it stays sensitive through quiet verses and loud choruses alike, rather
    than needing a fixed level tuned for one section of the song. Each band
    tracks its own history/average independently, since bass, mid, and
    treble content sit at very different absolute energy levels.
    """

    def __init__(self, label: str, band_low: float, band_high: float,
                 sensitivity: float, min_energy: float, debug: bool = False) -> None:
        self.label = label
        self.sos = butter(4, [band_low, band_high], btype="bandpass",
                           fs=SAMPLE_RATE, output="sos")
        # start the filter at rest (stream begins from silence); sosfilt_zi
        # would assume the input had been a constant 1.0 and inject a
        # spurious startup transient into the band
        self.zi = np.zeros((self.sos.shape[0], 2))
        self.sensitivity = sensitivity
        self.min_energy = min_energy  # absolute floor -- near-silence can never "beat"
        self.debug = debug
        history_len = max(1, round(HISTORY_SECONDS / FRAME_INTERVAL))
        self.history: deque[float] = deque(maxlen=history_len)
        self.last_beat = 0.0
        self.pending_energy = 0.0
        # feed() runs on the audio callback thread, tick() on the main
        # thread; the lock keeps the peak-hold read-and-reset atomic
        self._lock = threading.Lock()

    def feed(self, samples: np.ndarray) -> None:
        """Call from the audio callback with each raw mono block."""
        filtered, self.zi = sosfilt(self.sos, samples, zi=self.zi)
        block_energy = float(np.mean(filtered ** 2))
        with self._lock:
            if block_energy > self.pending_energy:
                self.pending_energy = block_energy  # hold the loudest block

    def tick(self) -> bool:
        """Call once per FRAME_INTERVAL. Returns True if a beat just hit."""
        with self._lock:
            energy, self.pending_energy = self.pending_energy, 0.0
        self.history.append(energy)
        avg = sum(self.history) / len(self.history)
        if avg <= 0 or energy < self.min_energy:
            if self.debug:
                print(f"[{self.label}] energy={energy:.3e} avg={avg:.3e} "
                      f"(below floor {self.min_energy:.3e})", file=sys.stderr)
            return False
        variance = sum((e - avg) ** 2 for e in self.history) / len(self.history)
        # More pronounced dynamics (higher variance relative to the average)
        # need less margin above average to trust a spike as a real beat.
        relative_variance = variance / (avg ** 2)
        threshold = max(1.05, self.sensitivity - relative_variance * 0.1)
        now = time.monotonic()
        is_beat = energy > threshold * avg and now - self.last_beat > REFRACTORY_SECONDS
        if self.debug:
            print(f"[{self.label}] energy={energy:.3e} avg={avg:.3e} threshold_x={threshold:.2f} "
                  f"need={threshold * avg:.3e} {'BEAT' if is_beat else ''}", file=sys.stderr)
        if is_beat:
            self.last_beat = now
            return True
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", help="Home Assistant IP/hostname")
    ap.add_argument("--port", type=int, default=8737)
    ap.add_argument("--device", help="capture device index or name substring")
    ap.add_argument("--color", metavar="RRGGBB",
                    help="fixed base color (default: white)")
    ap.add_argument("--cycle", action="store_true",
                    help="advance through the app's 7-color palette on every beat, instead of a fixed color")
    ap.add_argument("--bass-low", type=float, default=50.0, help="bass band low edge Hz (kick thump)")
    ap.add_argument("--bass-high", type=float, default=150.0, help="bass band high edge Hz")
    ap.add_argument("--weight-bass", type=float, default=1.0, help="flash strength for a bass hit (default 1.0)")
    ap.add_argument("--mid-low", type=float, default=200.0, help="mid band low edge Hz (snare body)")
    ap.add_argument("--mid-high", type=float, default=2000.0, help="mid band high edge Hz")
    ap.add_argument("--weight-mid", type=float, default=0.5, help="flash strength for a mid hit (default 0.5)")
    ap.add_argument("--treble-low", type=float, default=3000.0, help="treble band low edge Hz (snare crack/hi-hat)")
    ap.add_argument("--treble-high", type=float, default=8000.0, help="treble band high edge Hz")
    ap.add_argument("--weight-treble", type=float, default=0.7, help="flash strength for a treble hit (default 0.7)")
    ap.add_argument("--sensitivity", type=float, default=1.3,
                    help="beat threshold multiplier, shared by all bands -- lower means more sensitive (default 1.3)")
    ap.add_argument("--gain", type=float, default=1.0,
                    help="output brightness multiplier (default 1.0)")
    ap.add_argument("--min-energy", type=float, default=3e-5,
                    help="absolute noise floor, shared by all bands -- energy below this never beats, "
                         "regardless of ratio (default 3e-5; raise if silence still pulses, "
                         "lower if quiet real hits get missed)")
    ap.add_argument("--debug", action="store_true",
                    help="print each band's energy/threshold every tick to stderr")
    ap.add_argument("--list-devices", action="store_true")
    args = ap.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return
    if not args.host:
        ap.error("--host is required (or use --list-devices)")

    base_color = (255, 255, 255)  # default: white, scaled by the beat flash
    if args.color:
        raw = args.color.removeprefix("#")
        if len(raw) != 6:
            ap.error(f"--color must be 6 hex digits (RRGGBB), got {args.color!r}")
        try:
            v = int(raw, 16)
        except ValueError:
            ap.error(f"--color must be 6 hex digits (RRGGBB), got {args.color!r}")
        base_color = ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (args.host, args.port)

    bands = [
        (BandDetector("bass", args.bass_low, args.bass_high, args.sensitivity,
                      args.min_energy, args.debug), args.weight_bass),
        (BandDetector("mid", args.mid_low, args.mid_high, args.sensitivity,
                      args.min_energy, args.debug), args.weight_mid),
        (BandDetector("treble", args.treble_low, args.treble_high, args.sensitivity,
                      args.min_energy, args.debug), args.weight_treble),
    ]

    def on_audio(indata, _frames, _time, status) -> None:
        if status:
            print(status, file=sys.stderr)
        mono = indata[:, 0]
        for detector, _weight in bands:
            detector.feed(mono)

    level = 0.0
    palette_i = 0
    device = args.device
    if device is not None and device.isdigit():
        device = int(device)

    with sd.InputStream(device=device, channels=1, samplerate=SAMPLE_RATE,
                        blocksize=BLOCK_SIZE, callback=on_audio):
        info = sd.query_devices(device, "input") if device is not None else \
            sd.query_devices(kind="input")
        print(f"capturing from: {info['name']}  ->  udp://{dest[0]}:{dest[1]}")
        print(f"bass {args.bass_low:.0f}-{args.bass_high:.0f}Hz (w={args.weight_bass}), "
              f"mid {args.mid_low:.0f}-{args.mid_high:.0f}Hz (w={args.weight_mid}), "
              f"treble {args.treble_low:.0f}-{args.treble_high:.0f}Hz (w={args.weight_treble}), "
              f"sensitivity {args.sensitivity}")
        print("Ctrl-C to stop (HA's watchdog restores the lamp ~5 s later)")
        try:
            next_tick = time.monotonic() + FRAME_INTERVAL
            while True:
                # deadline-based scheduling: a bare sleep(FRAME_INTERVAL)
                # accumulates processing time and drifts below 20 Hz
                time.sleep(max(0.0, next_tick - time.monotonic()))
                next_tick += FRAME_INTERVAL
                hit_weight = max(
                    (weight for detector, weight in bands if detector.tick()),
                    default=None,
                )
                if hit_weight is not None:
                    # a weak-band hit must never dim a still-bright flash
                    level = max(hit_weight, level * DECAY)
                    if args.cycle:
                        palette_i = (palette_i + 1) % len(PALETTE)
                else:
                    level *= DECAY
                amp = round(min(1.0, level * args.gain) * 100)

                color = PALETTE[palette_i] if args.cycle else base_color
                r, g, b = (round(c * amp / 100) for c in color)
                sock.sendto(bytes([r, g, b]), dest)
        except KeyboardInterrupt:
            print("\nstopped.")


if __name__ == "__main__":
    main()
