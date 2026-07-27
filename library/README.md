# duoco-stripx

Python BLE control library for **duoCo StripX** LED strip / floor-lamp
controllers (BLE name prefix `MELK-`, vendor Shenzhen Shuanghongyuan).

The protocol was reverse-engineered from the duoCo StripX Android app and
**device-verified against a real `MELK-OC21` corner floor lamp** — see the
full byte-level spec in the companion `protocol/duoCo-StripX-BLE-protocol.md`.

## Device model

- GATT service `FFF0`, write characteristic `FFF3`, 9-byte frames
  `7E <len> <op> <payload…> EF`, write-without-response, no checksum.
- **Write-only**: no state read-back (the FFF3 read returns a constant
  device-ID string). State is tracked **optimistically**.
- **One BLE connection at a time** — while you hold it, the phone app can't.
- `MELK-OC21` specifics: RGB-only (no white/CCT channel), addressable
  80-pixel strip, built-in microphone with 8 visualizer modes.

## Usage

```python
from bleak import BleakScanner
from duoco_stripx import DuocoStripXDevice, MicEqMode, ANIMATION_NAME_TO_ID

ble_device = await BleakScanner.find_device_by_name("MELK-OC21")
lamp = DuocoStripXDevice(ble_device)

await lamp.set_power(True)
await lamp.set_rgb(255, 64, 0)
await lamp.set_brightness(128)                      # 0-255 scale
await lamp.set_effect(ANIMATION_NAME_TO_ID["7-Color Jump"])
await lamp.set_speed(80)
await lamp.set_scene(1)                             # Sunrise

# Built-in mic (quirk handling included: EQ engages, off restores the look)
await lamp.set_mic_eq(MicEqMode.SPECTRUM)
await lamp.set_mic(True)
await lamp.set_mic_sensitivity(80)
await lamp.set_mic(False)

await lamp.disconnect()
```

### Music-amplitude streaming

The lamp pulses to a ~10 Hz stream of `[7]=0x20` color frames (a single frame
does nothing). Loudness is encoded as color brightness; black = silence.

```python
amp = 80  # 0-100
r, g, b = (round(c * amp / 100) for c in (255, 0, 255))
await lamp.stream_music_frame(r, g, b)  # ~every 100 ms
await lamp.restore_state()  # when done — un-freezes the lamp
```

See `examples/music_streamer.py` for a complete system-audio → UDP →
Home Assistant pipeline (pairs with the `duoco_stripx` HA custom component).

### Expert / persistent settings — read before using

- `set_symphony_point(n)` — addressable pixel count; **persists in NVRAM**.
  Must equal the physical LED count (80 on `MELK-OC21`); smaller values leave
  the far end of the strip dark.
- `set_pin_sequence(b2, b1, b0)` — RGB wire-order remap; **persists**. The
  lamp ships correctly configured; the app's "default" `0x010203` actually
  swaps R↔G on `MELK-OC21` (whose correct value is `0x020103`). Don't send
  unless deliberately re-wiring.
- `protocol.system_time()` / `protocol.timing_status()` — on-device RTC
  alarms (frame builders only; `weeks` bit7 = enable).

## Development

```
uv venv && uv pip install -e ".[dev]"
pytest                       # byte-for-byte spec conformance + table integrity
python scripts/gen_effects.py <path-to-arrays.xml>   # regenerate effects.py
```
