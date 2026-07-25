"""Base entity for duoCo StripX."""
from __future__ import annotations

from duoco_stripx import DuocoStripXDevice, DuocoStripXState
from homeassistant.components import bluetooth
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import DuocoStripXConfigEntry


class DuocoStripXEntity(Entity):
    """Common behavior: device info, optimistic-state callbacks, availability."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: DuocoStripXConfigEntry) -> None:
        self._device: DuocoStripXDevice = entry.runtime_data.device
        self._address = (entry.unique_id or entry.data["address"]).upper()
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_BLUETOOTH, self._address)},
            name=self._device.name,
            manufacturer="Shenzhen Shuanghongyuan (duoCo)",
            model="StripX LED controller",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.register_callback(self._on_device_state))

    @callback
    def _on_device_state(self, _state: DuocoStripXState) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return bluetooth.async_address_present(
            self.hass, self._address, connectable=True
        )
