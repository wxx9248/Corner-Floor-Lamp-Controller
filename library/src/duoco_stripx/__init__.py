"""duoco-stripx — BLE control for duoCo StripX (MELK-) LED controllers.

Protocol reverse-engineered from the duoCo StripX Android app and
device-verified against a MELK-OC21 corner floor lamp.
"""
from __future__ import annotations

from . import protocol
from .const import (
    DEVICE_ID_MELK_OC21,
    MELK_OC21_PIXEL_COUNT,
    MIC_EQ_NAMES,
    MUSIC_PALETTE,
    NAME_PREFIX,
    SERVICE_UUID,
    WRITE_UUID,
    LightMode,
    MicEqMode,
)
from .device import DuocoStripXDevice
from .effects import (
    ANIMATION_MODES,
    ANIMATION_NAME_TO_ID,
    SCENE_NAME_TO_ID,
    SCENES,
)
from .models import DuocoStripXState

__version__ = "0.1.0"

__all__ = [
    "ANIMATION_MODES",
    "ANIMATION_NAME_TO_ID",
    "DEVICE_ID_MELK_OC21",
    "DuocoStripXDevice",
    "DuocoStripXState",
    "LightMode",
    "MELK_OC21_PIXEL_COUNT",
    "MIC_EQ_NAMES",
    "MUSIC_PALETTE",
    "MicEqMode",
    "NAME_PREFIX",
    "SCENE_NAME_TO_ID",
    "SCENES",
    "SERVICE_UUID",
    "WRITE_UUID",
    "protocol",
]
