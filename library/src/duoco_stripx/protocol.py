"""Pure 9-byte frame builders for the duoCo StripX BLE protocol.

Direct port of the device-verified builders in the reverse-engineering
harness (protocol/verify/lamp.py), which mirror
com.easylink.colorful.service.BluetoothLEService byte-for-byte.

Every function returns exactly 9 bytes: 7E <len> <op> <payload...> EF.
No checksum exists anywhere in the protocol.

Value ranges: percents are 0-100, RGB components 0-255.
"""
from __future__ import annotations

from .const import FRAME_END, FRAME_LEN, FRAME_START


def _frame(
    b1: int,
    op: int,
    p3: int = 0xFF,
    p4: int = 0xFF,
    p5: int = 0xFF,
    p6: int = 0xFF,
    p7: int = 0x00,
) -> bytes:
    frame = bytes([FRAME_START, b1, op, p3, p4, p5, p6, p7, FRAME_END])
    assert len(frame) == FRAME_LEN
    return frame


def hexf(frame: bytes) -> str:
    """Render a frame as spaced hex, e.g. '7E 04 04 01 00 01 FF 00 EF'."""
    return " ".join(f"{b:02X}" for b in frame)


# ---- core lighting (spec §4) ----

def power(on: bool) -> bytes:
    """§4.1 power on/off."""
    v = 1 if on else 0
    return _frame(0x04, 0x04, v, 0x00, v, 0xFF, 0x00)


def brightness(percent: int, mode: int = 0) -> bytes:
    """§4.2 brightness 0-100. mode: LightMode (0=ALL is the safe default)."""
    return _frame(0x04, 0x01, percent & 0xFF, mode & 0xFF, 0xFF, 0xFF, 0x00)


def rgb(r: int, g: int, b: int) -> bytes:
    """§4.3 RGB color, [7]=0x10 (RGB render target)."""
    return _frame(0x07, 0x05, 0x03, r & 0xFF, g & 0xFF, b & 0xFF, 0x10)


def cct(warm: int, cold: int) -> bytes:
    """§4.4 color temperature (complementary 0-100 pair), [7]=0x08.

    NO-OP on RGB-only hardware such as MELK-OC21: the frame is accepted but
    drives absent white LEDs, producing no light.
    """
    return _frame(0x06, 0x05, 0x02, warm & 0xFF, cold & 0xFF, 0xFF, 0x08)


def mode(mode_id: int) -> bytes:
    """§4.5 animation/effect mode, id 0-212 (see effects.ANIMATION_MODES)."""
    return _frame(0x05, 0x03, mode_id & 0xFF, 0x06, 0xFF, 0xFF, 0x00)


def speed(percent: int) -> bytes:
    """§4.6 effect speed 0-100."""
    return _frame(0x04, 0x02, percent & 0xFF, 0xFF, 0xFF, 0xFF, 0x00)


def scene(scene_id: int) -> bytes:
    """§4.7 scene, id 1-28 (see effects.SCENES)."""
    return _frame(0x05, 0x31, scene_id & 0xFF, 0x07, 0xFF, 0xFF, 0x01)


def single_color(pos: int) -> bytes:
    """§4.8 whole-strip color by palette position 0-100, [7]=0x08.

    NO-OP on RGB-only hardware (white/CCT render target) — use rgb() instead.
    """
    return _frame(0x05, 0x05, 0x01, pos & 0xFF, 0xFF, 0xFF, 0x08)


# ---- mic / music (spec §6, §6.1) ----

def mic_on(on: bool) -> bytes:
    """§6 mic on/off.

    Device-confirmed quirks (spec §6.1): engaging reactive mode needs an EQ
    frame (mic_eq) sent after this. Disengaging freezes the last waveform —
    re-assert a color/effect afterward to unfreeze it.
    """
    return _frame(0x04, 0x07, 1 if on else 0, 0xFF, 0xFF, 0xFF, 0x00)


def mic_sensitive(sensitivity: int) -> bytes:
    """§6 mic sensitivity 0-100."""
    return _frame(0x04, 0x06, sensitivity & 0xFF, 0xFF, 0xFF, 0xFF, 0x00)


def mic_eq(eq: int) -> bytes:
    """§6 mic EQ visualizer mode 0-7 ([3] = 0x80 + eq). Engages reactive mode."""
    return _frame(0x07, 0x03, (0x80 + eq) & 0xFF, 0x04, 0xFF, 0xFF, 0x00)


def music_amp(r: int, g: int, b: int) -> bytes:
    """§6 music-amplitude frame, [7]=0x20 (music render target).

    Streaming-only: a single frame is ignored; stream ~10 Hz to make the lamp
    pulse. Encode loudness as color brightness; black (0,0,0) = silence.
    """
    return _frame(0x07, 0x05, 0x03, r & 0xFF, g & 0xFF, b & 0xFF, 0x20)


# ---- device configuration (spec §6, §6.1 — use with care) ----

def symphony(count: int) -> bytes:
    """§6 addressable pixel count, 16-bit little-endian. Persists in NVRAM.

    WARNING: must equal the physical pixel count (80 on MELK-OC21); a smaller
    value permanently truncates the lit length until rewritten.
    """
    return _frame(0x07, 0x21, count & 0xFF, (count >> 8) & 0xFF, 0x00, 0xFF, 0x00)


def pin_sequence(b2: int, b1: int, b0: int) -> bytes:
    """§6 RGB channel wire-order remap (24-bit, [3]=b2 [4]=b1 [5]=b0).

    WARNING: persists in NVRAM and the lamp ships correctly configured — never
    send unless deliberately re-wiring. The app's default 0x010203 SWAPS R<->G
    on MELK-OC21 (correct value for that unit: 0x020103).
    """
    return _frame(0x06, 0x81, b2 & 0xFF, b1 & 0xFF, b0 & 0xFF, 0xFF, 0x00)


# ---- clock / scheduling (spec §6, §6.1) ----

def system_time(hour: int, minute: int, second: int, weekday: int) -> bytes:
    """§6 set the lamp's RTC. Required before timing_status alarms work."""
    return _frame(0x07, 0x83, hour & 0xFF, minute & 0xFF, second & 0xFF, weekday & 0xFF, 0xFF)


def timing_status(hour: int, minute: int, second: int, slot: int, weeks: int) -> bytes:
    """§6 on-device alarm. slot: 0=turn-on, 1=turn-off.

    weeks: bit7 (0x80) = ENABLE, bits0-6 = weekday mask (0xFF = every day).
    An alarm with bit7 clear is stored but disabled.
    """
    return _frame(0x08, 0x82, hour & 0xFF, minute & 0xFF, second & 0xFF, slot & 0xFF, weeks & 0xFF)
