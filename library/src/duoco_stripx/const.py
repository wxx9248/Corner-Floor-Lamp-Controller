"""Constants for the duoCo StripX BLE protocol.

Derived from the reverse-engineered, device-verified protocol spec
(duoCo-StripX-BLE-protocol.md). All values were confirmed against a live
MELK-OC21 unit.
"""
from __future__ import annotations

from enum import IntEnum

# GATT layout (spec §2)
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"

# Discovery (spec §1)
NAME_PREFIX = "MELK-"

# FFF3 GATT read returns this constant device-ID string on MELK-OC21 —
# a firmware/model fingerprint, NOT dynamic state (spec §2).
DEVICE_ID_MELK_OC21 = "P30_SHY_28_R1380"

# Framing (spec §3.1)
FRAME_START = 0x7E
FRAME_END = 0xEF
FRAME_LEN = 9

# Recommended minimum gap between back-to-back frames (spec §3.3).
WRITE_GAP = 0.03  # seconds

# MELK-OC21 is an addressable strip with exactly 80 pixels (spec §6.1).
# The symphony/pixel-count value persists in lamp NVRAM and ships correct;
# never set it below the physical pixel count.
MELK_OC21_PIXEL_COUNT = 80


class LightMode(IntEnum):
    """Target sub-light selector (BluetoothUtil.LightMode)."""

    ALL = 0
    RGB = 1
    W = 2
    CT = 3


class MicEqMode(IntEnum):
    """Built-in-mic visualizer modes (BluetoothUtil.ExternalMicEqMode).

    All 8 device-confirmed on MELK-OC21 (spec §6.1 table).
    """

    ENERGIC = 0
    RHYTHM = 1
    SPECTRUM = 2
    ROLLING = 3
    ENERGIC_TWO = 4
    RHYTHM_TWO = 5
    SPECTRUM_TWO = 6
    ROLLING_TWO = 7


MIC_EQ_NAMES: dict[MicEqMode, str] = {
    MicEqMode.ENERGIC: "Energic",
    MicEqMode.RHYTHM: "Rhythm",
    MicEqMode.SPECTRUM: "Spectrum",
    MicEqMode.ROLLING: "Rolling",
    MicEqMode.ENERGIC_TWO: "Energic Two",
    MicEqMode.RHYTHM_TWO: "Rhythm Two",
    MicEqMode.SPECTRUM_TWO: "Spectrum Two",
    MicEqMode.ROLLING_TWO: "Rolling Two",
}

# The app cycles the music-streaming color through this palette, one step per
# frame (Utils.musicColors: R, G, B, Y, M, C, W).
MUSIC_PALETTE: tuple[tuple[int, int, int], ...] = (
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
    (255, 255, 255),
)
