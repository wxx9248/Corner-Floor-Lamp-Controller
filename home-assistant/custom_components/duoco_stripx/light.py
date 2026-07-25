"""The main light entity: power, brightness, RGB, effects + scenes.

The MELK-OC21 hardware is RGB-only (no white/CCT channel), so only
ColorMode.RGB is exposed — color_temp frames would produce no light.
State is optimistic (the lamp is write-only).
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from duoco_stripx import (
    ANIMATION_MODES,
    ANIMATION_NAME_TO_ID,
    SCENE_NAME_TO_ID,
    SCENES,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuocoStripXConfigEntry
from .const import SCENE_EFFECT_PREFIX
from .entity import DuocoStripXEntity

EFFECT_LIST = list(ANIMATION_MODES.values()) + [
    f"{SCENE_EFFECT_PREFIX}{name}" for name in SCENES.values()
]

SERVICE_SEND_RAW = "send_raw"
SERVICE_SET_SYMPHONY_POINT = "set_symphony_point"
SERVICE_SET_PIN_SEQUENCE = "set_pin_sequence"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DuocoStripXConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([DuocoStripXLight(entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SEND_RAW,
        {vol.Required("frame"): cv.string},
        "async_send_raw",
    )
    platform.async_register_entity_service(
        SERVICE_SET_SYMPHONY_POINT,
        {vol.Required("count"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1024))},
        "async_set_symphony_point",
    )
    platform.async_register_entity_service(
        SERVICE_SET_PIN_SEQUENCE,
        {
            vol.Required("b2"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Required("b1"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Required("b0"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        },
        "async_set_pin_sequence",
    )


class DuocoStripXLight(DuocoStripXEntity, LightEntity):
    """RGB light with the full effect + scene catalog."""

    _attr_name = None  # main entity: takes the device name
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = EFFECT_LIST
    _attr_assumed_state = True  # optimistic: the lamp has no state read-back

    def __init__(self, entry: DuocoStripXConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = self._address

    # ---- state (from the library's optimistic model) ----

    @property
    def is_on(self) -> bool:
        return self._device.state.power

    @property
    def brightness(self) -> int:
        return self._device.state.brightness

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        return self._device.state.rgb

    @property
    def effect(self) -> str | None:
        state = self._device.state
        if state.effect_id is not None:
            return ANIMATION_MODES.get(state.effect_id)
        if state.scene_id is not None:
            return f"{SCENE_EFFECT_PREFIX}{SCENES.get(state.scene_id)}"
        return None

    # ---- commands ----

    async def async_turn_on(self, **kwargs: Any) -> None:
        device = self._device
        if not device.state.power:
            await device.set_power(True)
        if (effect := kwargs.get(ATTR_EFFECT)) is not None:
            if effect.startswith(SCENE_EFFECT_PREFIX):
                await device.set_scene(
                    SCENE_NAME_TO_ID[effect[len(SCENE_EFFECT_PREFIX):]]
                )
            else:
                await device.set_effect(ANIMATION_NAME_TO_ID[effect])
        elif (rgb := kwargs.get(ATTR_RGB_COLOR)) is not None:
            await device.set_rgb(*rgb)
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            await device.set_brightness(brightness)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        await self._device.set_power(False)

    # ---- expert entity services ----

    async def async_send_raw(self, frame: str) -> None:
        """Send a raw 9-byte frame given as hex (e.g. '7E0404010001FF00EF')."""
        data = bytes.fromhex(frame.replace(" ", ""))
        if len(data) != 9 or data[0] != 0x7E or data[-1] != 0xEF:
            raise ValueError("frame must be 9 bytes: 7E ... EF")
        await self._device.send_raw(data)

    async def async_set_symphony_point(self, count: int) -> None:
        """Set the addressable pixel count (80 on MELK-OC21). Persists."""
        await self._device.set_symphony_point(count)

    async def async_set_pin_sequence(self, b2: int, b1: int, b0: int) -> None:
        """Remap RGB wire order. Persists — expert/re-wiring use only."""
        await self._device.set_pin_sequence(b2, b1, b0)
