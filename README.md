# Corner Floor Lamp Controller

Reverse-engineered BLE protocol and Home Assistant integration for the
**duoCo StripX** LED strip / floor-lamp controllers (BLE name prefix
`MELK-`) — built from a real `MELK-OC21` corner floor lamp and the "duoCo
StripX" Android app (`com.easylink.colorful`).

The protocol is fully device-verified: power, brightness, RGB color, 213
animation modes, 28 scenes, effect speed, the built-in microphone's 8
sound-reactive visualizers, addressable-pixel count, RGB wire-order, on-device
RTC alarms, and music-amplitude streaming.

## Layout

| Path | What it is |
|---|---|
| [`library/`](library) | `duoco-stripx` — standalone Python BLE control library (bleak). [README](library/README.md) |
| [`home-assistant/`](home-assistant) | Home Assistant custom component built on the library — light, mic controls, UDP music-streaming ingest. [README](home-assistant/README.md) |
| `scripts/` | Release tooling: version stamping, HA-import compatibility check |
| `.github/workflows/` | CI (build check, HA-compatibility check against latest HA) and manual release |

The protocol reverse-engineering workspace (decompiled app sources, vendor
APK, raw verification scripts) is kept in a separate local, unpublished
directory and is not part of this repository.

## Quick start

- **Just want the lamp in Home Assistant?** → [`home-assistant/README.md`](home-assistant/README.md)
  (install from the latest [release](../../releases), auto-discovery, entity
  list, music streaming, HA-automation scheduling examples).
- **Want to control the lamp from Python directly?** → [`library/README.md`](library/README.md)

## Versioning & releases

Version fields committed to this repo are always `0.0.0` placeholders — real
versions exist only as `vX.Y.Z` git tags, created by the manual **Release**
GitHub Actions workflow (`major`/`minor`/`patch` bump from the latest tag),
which builds and publishes the library wheel and a ready-to-install Home
Assistant component zip as release assets. Every push and PR additionally
runs a build-check + Home-Assistant-compatibility CI workflow.

## Hardware notes

- GATT service `FFF0`, write characteristic `FFF3`, 9-byte frames
  `7E <len> <op> <payload…> EF`, write-without-response, no checksum.
- **Write-only** — no state read-back; the integration and library track
  state optimistically.
- **One BLE connection at a time** — while Home Assistant (or the library)
  holds it, the phone app can't connect, and vice versa.
- `MELK-OC21` is RGB-only (no white/CCT channel) and addressable at 80 pixels.
