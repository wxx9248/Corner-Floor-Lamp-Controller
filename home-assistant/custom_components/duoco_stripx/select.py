"""Select: the 8 built-in-mic EQ visualizer modes (all device-confirmed)."""
from __future__ import annotations

from duoco_stripx import MIC_EQ_NAMES, MicEqMode
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuocoStripXConfigEntry
from .entity import DuocoStripXEntity

NAME_TO_EQ = {name: eq for eq, name in MIC_EQ_NAMES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DuocoStripXConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([DuocoStripXEqSelect(entry)])


class DuocoStripXEqSelect(DuocoStripXEntity, SelectEntity):
    """Visualizer selection. Applies live while Sound reactive is on;
    otherwise takes effect on the next engage."""

    _attr_name = "Mic visualizer"
    _attr_icon = "mdi:waveform"
    _attr_options = [MIC_EQ_NAMES[MicEqMode(i)] for i in range(8)]

    def __init__(self, entry: DuocoStripXConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{self._address}_mic_eq"

    @property
    def current_option(self) -> str:
        return MIC_EQ_NAMES[self._device.state.mic_eq]

    async def async_select_option(self, option: str) -> None:
        await self._device.set_mic_eq(NAME_TO_EQ[option])
