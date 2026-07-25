"""duoCo StripX BLE integration (MELK- LED strip / floor-lamp controllers)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from duoco_stripx import DuocoStripXDevice
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_UDP_PORT, DEFAULT_UDP_PORT
from .stream import MusicStreamer

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.LIGHT, Platform.NUMBER, Platform.SELECT, Platform.SWITCH]


@dataclass
class DuocoStripXData:
    """Runtime data for a config entry."""

    device: DuocoStripXDevice
    streamer: MusicStreamer


type DuocoStripXConfigEntry = ConfigEntry[DuocoStripXData]


async def async_setup_entry(
    hass: HomeAssistant, entry: DuocoStripXConfigEntry
) -> bool:
    """Set up a lamp from a config entry."""
    address: str = entry.unique_id or entry.data["address"]
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), connectable=True
    )
    if ble_device is None:
        raise ConfigEntryNotReady(
            f"duoCo StripX {address} not found — is it in Bluetooth range?"
        )

    device = DuocoStripXDevice(ble_device)
    streamer = MusicStreamer(
        device, entry.options.get(CONF_UDP_PORT, DEFAULT_UDP_PORT)
    )
    entry.runtime_data = DuocoStripXData(device=device, streamer=streamer)

    @callback
    def _async_on_advertisement(
        service_info: BluetoothServiceInfoBleak, _change: BluetoothChange
    ) -> None:
        # keep the BLEDevice fresh for reconnects
        device.update_ble_device(service_info.device)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_on_advertisement,
            BluetoothCallbackMatcher(address=address.upper(), connectable=True),
            BluetoothScanningMode.PASSIVE,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DuocoStripXConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = entry.runtime_data
        await data.streamer.stop(restore=False)
        await data.device.stop()
    return unload_ok
