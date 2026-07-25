"""Switches: built-in-mic sound-reactive mode, and music-streaming arm/disarm."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuocoStripXConfigEntry
from .entity import DuocoStripXEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DuocoStripXConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [DuocoStripXMicSwitch(entry), DuocoStripXMusicStreamSwitch(entry)]
    )


class DuocoStripXMicSwitch(DuocoStripXEntity, SwitchEntity):
    """Sound-reactive mode via the lamp's built-in microphone.

    Turning on sends mic-on + the selected EQ visualizer (the EQ frame is what
    actually engages reactive mode); turning off restores the previous look
    (mic-off alone freezes the last waveform).
    """

    _attr_name = "Sound reactive"
    _attr_icon = "mdi:microphone-music"
    _attr_assumed_state = True

    def __init__(self, entry: DuocoStripXConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{self._address}_mic"

    @property
    def is_on(self) -> bool:
        return self._device.state.mic_on

    async def async_turn_on(self, **_kwargs: Any) -> None:
        await self._device.set_mic(True)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        await self._device.set_mic(False)


class DuocoStripXMusicStreamSwitch(DuocoStripXEntity, SwitchEntity):
    """Arms the UDP music-streaming ingest (see stream.py for the format).

    Auto-disarms (watchdog) after 5 s without packets, restoring the lamp.
    """

    _attr_name = "Music streaming"
    _attr_icon = "mdi:speaker-wireless"

    def __init__(self, entry: DuocoStripXConfigEntry) -> None:
        super().__init__(entry)
        self._streamer = entry.runtime_data.streamer
        self._attr_unique_id = f"{self._address}_music_stream"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._streamer.register_state_callback(self._on_streamer_state)
        )

    @callback
    def _on_streamer_state(self, _active: bool) -> None:
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        return self._streamer.active

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        return {"udp_port": self._streamer.port}

    async def async_turn_on(self, **_kwargs: Any) -> None:
        await self._streamer.start()

    async def async_turn_off(self, **_kwargs: Any) -> None:
        await self._streamer.stop()
