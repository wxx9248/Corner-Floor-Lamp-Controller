# duoCo StripX — Home Assistant integration

Controls duoCo StripX BLE LED controllers (name prefix `MELK-`, e.g. the
`MELK-OC21` corner floor lamp) natively through Home Assistant's Bluetooth
stack. Local push, no cloud, works through ESPHome Bluetooth proxies.

Built on the [`duoco-stripx`](../library) library and the
device-verified protocol spec (`protocol/duoCo-StripX-BLE-protocol.md`).

## Install

1. Download `duoco_stripx-component-<version>.zip` from the repo's **latest
   GitHub release** and unzip it into your HA `config/custom_components/`
   (creates `custom_components/duoco_stripx/`).
2. Restart Home Assistant — it automatically pip-installs the matching
   `duoco-stripx` wheel from the same release (the zip's `manifest.json`
   points at it).
3. The lamp is auto-discovered (Settings → Devices — "duoCo StripX"); or add
   it manually via *Add integration → duoCo StripX*.

> Don't copy `custom_components/duoco_stripx/` from the repo working tree for
> a real install: committed version fields are `0.0.0` placeholders and the
> manifest points at a wheel that doesn't exist. Real versions are stamped by
> the release workflow. For local dev, `pip install -e ./library` into HA's
> environment and copy the component as-is.

### Releasing a new version

Versions live only in git tags (`vX.Y.Z`); the repo always commits `0.0.0`.
GitHub → *Actions → Release → Run workflow* → pick `major`/`minor`/`patch`.
The workflow bumps from the latest tag, runs the tests, stamps the version
(`scripts/set_version.py`), builds the wheel + component zip, pushes the tag,
and publishes the release. PRs and pushes only run the build-check CI — no
releases.

> ⚠️ The lamp accepts **one** BLE connection. While HA controls it, the phone
> app cannot connect (and vice versa — close the app if discovery fails).

## Entities

| Entity | What it does |
|---|---|
| `light.<lamp>` | on/off, brightness, RGB color, 213 effects + 28 scenes (`Scene: …`) |
| `number.<lamp>_effect_speed` | animation speed 0–100 |
| `switch.<lamp>_sound_reactive` | built-in-mic reactive mode (handles the engage/restore quirks) |
| `select.<lamp>_mic_visualizer` | the 8 visualizers (Energic/Rhythm/Spectrum/Rolling + Two) |
| `number.<lamp>_mic_sensitivity` | mic sensitivity 0–100 |
| `switch.<lamp>_music_streaming` | arms the UDP music ingest (below) |
| `number.<lamp>_pixel_count` | ⚠️ advanced, disabled by default — see notes |

State is **optimistic** (the lamp is write-only); entities show what was last
commanded. `color_temp` is deliberately not exposed: this hardware is
RGB-only and CCT frames produce no light.

### Expert services (on the `light` entity)

`duoco_stripx.send_raw`, `duoco_stripx.set_symphony_point`,
`duoco_stripx.set_pin_sequence` — raw protocol access and the two persistent
NVRAM settings. Read the warnings in `services.yaml` first; in particular
never send a pin sequence unless you have re-wired the strip, and never set
the pixel count below the physical LED count (80 on MELK-OC21).

## Music streaming (lamp pulses to your audio)

The lamp reacts to a ~10 Hz stream of color frames. HA owns the BLE
connection, so it proxies: turn **on** `switch.<lamp>_music_streaming`, then
have any audio pipeline send UDP packets to `<ha-host>:8737` (port
configurable in the integration's options):

- `[0x41, amplitude]` (2 bytes, amplitude 0–100) — scales the lamp's current color
- `[0x44, R, G, B]` (4 bytes) — direct color

If packets stop for 5 s the integration auto-disarms and restores the
previous light state.

Reference pipeline (captures system audio on macOS/Linux):

```
pip install sounddevice numpy
python library/examples/music_streamer.py --host <ha-ip> --cycle
```

(macOS: route audio through a BlackHole loopback; Linux: use a
PipeWire/Pulse "monitor" source. See the script's header.)

## Scheduling (replaces the phone app's timers)

Use HA automations instead of the lamp's on-device RTC alarms — more flexible
and survives everything the lamp's two alarm slots don't:

```yaml
# fade in with the Sunrise scene at 07:00 on weekdays
automation:
  - alias: Lamp sunrise
    triggers:
      - trigger: time
        at: "07:00:00"
    conditions:
      - condition: time
        weekday: [mon, tue, wed, thu, fri]
    actions:
      - action: light.turn_on
        target: { entity_id: light.melk_oc21 }
        data: { effect: "Scene: Sunrise", brightness: 180 }

  - alias: Lamp off at midnight
    triggers:
      - trigger: time
        at: "00:00:00"
    actions:
      - action: light.turn_off
        target: { entity_id: light.melk_oc21 }
```
