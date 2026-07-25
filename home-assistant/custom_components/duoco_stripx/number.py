"""Numbers: effect speed, mic sensitivity, and (advanced) pixel count."""
from __future__ import annotations

from duoco_stripx import MELK_OC21_PIXEL_COUNT
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuocoStripXConfigEntry
from .entity import DuocoStripXEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DuocoStripXConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            DuocoStripXSpeedNumber(entry),
            DuocoStripXMicSensitivityNumber(entry),
            DuocoStripXPixelCountNumber(entry),
        ]
    )


class DuocoStripXSpeedNumber(DuocoStripXEntity, NumberEntity):
    """Effect/animation speed."""

    _attr_name = "Effect speed"
    _attr_icon = "mdi:speedometer"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1

    def __init__(self, entry: DuocoStripXConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{self._address}_speed"

    @property
    def native_value(self) -> int:
        return self._device.state.speed

    async def async_set_native_value(self, value: float) -> None:
        await self._device.set_speed(round(value))


class DuocoStripXMicSensitivityNumber(DuocoStripXEntity, NumberEntity):
    """Built-in mic sensitivity."""

    _attr_name = "Mic sensitivity"
    _attr_icon = "mdi:microphone-settings"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1

    def __init__(self, entry: DuocoStripXConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{self._address}_mic_sensitivity"

    @property
    def native_value(self) -> int:
        return self._device.state.mic_sensitivity

    async def async_set_native_value(self, value: float) -> None:
        await self._device.set_mic_sensitivity(round(value))


class DuocoStripXPixelCountNumber(DuocoStripXEntity, NumberEntity):
    """Addressable pixel count (symphony point). ADVANCED — persists in the
    lamp's NVRAM and ships correctly configured (80 on MELK-OC21).

    Only change it if the strip is visibly truncated, and only to the TRUE
    physical LED count: a smaller value leaves the far end of the strip dark.
    Disabled by default for safety.
    """

    _attr_name = "Pixel count (advanced)"
    _attr_icon = "mdi:led-strip-variant"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1
    _attr_native_max_value = 1024
    _attr_native_step = 1
    _attr_assumed_state = True

    def __init__(self, entry: DuocoStripXConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{self._address}_pixel_count"
        # not readable from the lamp; assume the MELK-OC21 factory value
        self._value = MELK_OC21_PIXEL_COUNT

    @property
    def native_value(self) -> int:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        await self._device.set_symphony_point(round(value))
        self._value = round(value)
        self.async_write_ha_state()
