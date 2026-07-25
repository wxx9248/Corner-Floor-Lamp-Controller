"""Optimistic state model for a duoCo StripX lamp.

The lamp has no dynamic state read-back (FFF3 read returns a constant device-ID
string), so clients must track what they last sent.
"""
from __future__ import annotations

from dataclasses import dataclass

from .const import MicEqMode


@dataclass
class DuocoStripXState:
    """Last-commanded (optimistic) lamp state.

    brightness is on the 0-255 scale (HA convention); it is converted to the
    lamp's 0-100 scale on the wire. Exactly one of rgb / effect_id / scene_id
    describes the current "look": setting a color clears effect/scene and vice
    versa.
    """

    power: bool = False
    brightness: int = 255
    rgb: tuple[int, int, int] = (255, 255, 255)
    effect_id: int | None = None
    scene_id: int | None = None
    speed: int = 50
    mic_on: bool = False
    mic_eq: MicEqMode = MicEqMode.ENERGIC
    mic_sensitivity: int = 50
