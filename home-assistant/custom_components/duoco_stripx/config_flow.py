"""Config flow: Bluetooth auto-discovery + manual pick, and options (UDP port)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from duoco_stripx import NAME_PREFIX, SERVICE_UUID
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import CONF_UDP_PORT, DEFAULT_UDP_PORT, DOMAIN


def _is_stripx(service_info: BluetoothServiceInfoBleak) -> bool:
    name = service_info.name or ""
    return name.startswith(NAME_PREFIX) or SERVICE_UUID in [
        u.lower() for u in service_info.service_uuids
    ]


class DuocoStripXConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle discovery and setup."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """A MELK-*/FFF0 device was discovered by the Bluetooth integration."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovery_info is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery_info.name or self._discovery_info.address,
                data={CONF_ADDRESS: self._discovery_info.address},
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery_info.name or self._discovery_info.address
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual add: pick from currently-visible lamps."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered[address], data={CONF_ADDRESS: address}
            )

        configured = self._async_current_ids()
        for service_info in bluetooth.async_discovered_service_info(
            self.hass, connectable=True
        ):
            if service_info.address in configured:
                continue
            if _is_stripx(service_info):
                self._discovered[service_info.address] = (
                    f"{service_info.name or 'MELK device'} ({service_info.address})"
                )
        if not self._discovered:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered)}
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> DuocoStripXOptionsFlow:
        return DuocoStripXOptionsFlow()


class DuocoStripXOptionsFlow(OptionsFlowWithReload):
    """Options: the music-streaming UDP port. Reloads the entry on change."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UDP_PORT,
                        default=self.config_entry.options.get(
                            CONF_UDP_PORT, DEFAULT_UDP_PORT
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1024, max=65535))
                }
            ),
        )
