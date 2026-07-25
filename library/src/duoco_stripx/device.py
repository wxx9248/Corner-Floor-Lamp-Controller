"""Connection management + high-level operations for a duoCo StripX lamp.

Wraps a bleak BLEDevice with:
- resilient connect (bleak-retry-connector), write-without-response to FFF3
- a write lock + minimum inter-frame gap (spec §3.3)
- optimistic state tracking (the lamp is write-only) with change callbacks
- the two device-confirmed mic quirks encapsulated (spec §6.1):
  * mic on alone doesn't engage reactive mode — the EQ frame does
  * mic off freezes the last waveform — the previous look is re-asserted
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import replace

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from . import protocol
from .const import MUSIC_PALETTE, WRITE_GAP, WRITE_UUID, MicEqMode
from .models import DuocoStripXState

_LOGGER = logging.getLogger(__name__)

DISCONNECT_DELAY = 90.0  # idle seconds before dropping the BLE connection


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


class DuocoStripXDevice:
    """A single duoCo StripX lamp (e.g. MELK-OC21)."""

    def __init__(self, ble_device: BLEDevice) -> None:
        self._ble_device = ble_device
        self._client: BleakClient | None = None
        self._connect_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._last_write = 0.0
        self._disconnect_timer: asyncio.TimerHandle | None = None
        self._expected_disconnect = False
        self._callbacks: list[Callable[[DuocoStripXState], None]] = []
        self._music_palette_index = 0
        self.state = DuocoStripXState()

    # ---- identity ----

    @property
    def address(self) -> str:
        return self._ble_device.address

    @property
    def name(self) -> str:
        return self._ble_device.name or self._ble_device.address

    def update_ble_device(self, ble_device: BLEDevice) -> None:
        """Feed in a fresh BLEDevice from a new advertisement."""
        self._ble_device = ble_device

    # ---- state callbacks ----

    def register_callback(
        self, callback: Callable[[DuocoStripXState], None]
    ) -> Callable[[], None]:
        self._callbacks.append(callback)

        def unregister() -> None:
            self._callbacks.remove(callback)

        return unregister

    def _fire_callbacks(self) -> None:
        for callback in self._callbacks:
            callback(self.state)

    def _update_state(self, **changes: object) -> None:
        self.state = replace(self.state, **changes)
        self._fire_callbacks()

    # ---- connection ----

    async def _ensure_connected(self) -> BleakClient:
        if self._client is not None and self._client.is_connected:
            return self._client
        async with self._connect_lock:
            if self._client is not None and self._client.is_connected:
                return self._client
            _LOGGER.debug("%s: connecting", self.name)
            self._client = await establish_connection(
                BleakClientWithServiceCache,
                self._ble_device,
                self.name,
                disconnected_callback=self._on_disconnect,
                ble_device_callback=lambda: self._ble_device,
            )
            _LOGGER.debug("%s: connected", self.name)
            return self._client

    def _on_disconnect(self, _client: BleakClient) -> None:
        self._client = None
        if not self._expected_disconnect:
            _LOGGER.debug("%s: unexpected disconnect", self.name)
        self._expected_disconnect = False

    def _reschedule_disconnect(self) -> None:
        if self._disconnect_timer is not None:
            self._disconnect_timer.cancel()
        loop = asyncio.get_running_loop()
        self._disconnect_timer = loop.call_later(
            DISCONNECT_DELAY, lambda: asyncio.create_task(self.disconnect())
        )

    async def disconnect(self) -> None:
        """Drop the BLE connection (the lamp allows only one at a time)."""
        if self._disconnect_timer is not None:
            self._disconnect_timer.cancel()
            self._disconnect_timer = None
        client, self._client = self._client, None
        if client is not None and client.is_connected:
            self._expected_disconnect = True
            await client.disconnect()

    async def stop(self) -> None:
        await self.disconnect()

    # ---- raw writes ----

    async def _write(self, frame: bytes, gap: float = WRITE_GAP) -> None:
        """Write one frame (write-without-response), honoring the min gap."""
        async with self._write_lock:
            wait = self._last_write + gap - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                client = await self._ensure_connected()
                await client.write_gatt_char(WRITE_UUID, frame, response=False)
            except (BleakError, OSError, TimeoutError):
                # one reconnect + retry
                _LOGGER.debug("%s: write failed, reconnecting", self.name)
                self._client = None
                client = await self._ensure_connected()
                await client.write_gatt_char(WRITE_UUID, frame, response=False)
            self._last_write = time.monotonic()
        self._reschedule_disconnect()

    async def _send(self, *frames: bytes) -> None:
        for frame in frames:
            await self._write(frame)

    async def send_raw(self, frame: bytes) -> None:
        """Send an arbitrary pre-built frame (expert use; no state tracking)."""
        await self._write(frame)

    # ---- high-level operations (optimistic state) ----

    async def set_power(self, on: bool) -> None:
        await self._send(protocol.power(on))
        self._update_state(power=on)

    async def set_brightness(self, brightness_255: int) -> None:
        """Brightness on the 0-255 scale (converted to the lamp's 0-100)."""
        brightness_255 = _clamp(brightness_255, 0, 255)
        percent = max(1, round(brightness_255 * 100 / 255)) if brightness_255 else 0
        await self._send(protocol.brightness(percent, 0))
        self._update_state(brightness=brightness_255)

    async def set_rgb(self, r: int, g: int, b: int) -> None:
        """Solid color; clears any active effect/scene."""
        await self._send(protocol.rgb(r, g, b))
        self._update_state(rgb=(r, g, b), effect_id=None, scene_id=None, power=True)

    async def set_effect(self, mode_id: int) -> None:
        """Animation mode 0-212 (effects.ANIMATION_MODES)."""
        await self._send(protocol.mode(mode_id))
        self._update_state(effect_id=mode_id, scene_id=None, power=True)

    async def set_scene(self, scene_id: int) -> None:
        """Scene 1-28 (effects.SCENES)."""
        await self._send(protocol.scene(scene_id))
        self._update_state(scene_id=scene_id, effect_id=None, power=True)

    async def set_speed(self, percent: int) -> None:
        await self._send(protocol.speed(_clamp(percent, 0, 100)))
        self._update_state(speed=_clamp(percent, 0, 100))

    # ---- built-in microphone ----

    async def set_mic(self, on: bool) -> None:
        """Engage/disengage sound-reactive mode.

        Engage: mic-on then EQ frame (the EQ frame is what actually switches
        into reactive mode). Disengage: mic-off then re-assert the previous
        look, because mic-off freezes the last waveform on the strip.
        """
        if on:
            await self._send(
                protocol.mic_on(True), protocol.mic_eq(int(self.state.mic_eq))
            )
            self._update_state(mic_on=True)
        else:
            await self._send(protocol.mic_on(False))
            self._update_state(mic_on=False)
            await self._assert_look()

    async def set_mic_eq(self, eq: MicEqMode | int) -> None:
        """Select a visualizer. If the mic is active, switches it live;
        otherwise just records the choice for the next engage."""
        eq = MicEqMode(eq)
        if self.state.mic_on:
            await self._send(protocol.mic_eq(int(eq)))
        self._update_state(mic_eq=eq)

    async def set_mic_sensitivity(self, percent: int) -> None:
        await self._send(protocol.mic_sensitive(_clamp(percent, 0, 100)))
        self._update_state(mic_sensitivity=_clamp(percent, 0, 100))

    # ---- music-amplitude streaming (spec §6.1: streaming-only) ----

    async def stream_music_frame(self, r: int, g: int, b: int) -> None:
        """Send one music frame ([7]=0x20). Stream ~10 Hz; black = silence.

        Does not touch optimistic state; call restore_state() when done
        streaming to un-freeze the lamp.
        """
        await self._write(protocol.music_amp(r, g, b), gap=0.0)

    async def stream_music_amplitude(
        self, amplitude: int, base_rgb: tuple[int, int, int] | None = None
    ) -> None:
        """Send one amplitude frame: base color scaled by amplitude 0-100.

        With base_rgb=None, cycles the app's 7-color music palette one step
        per frame. Unlike the app (whose HSV scaling clamps to full), this
        scales smoothly.
        """
        amplitude = _clamp(amplitude, 0, 100)
        if base_rgb is None:
            base_rgb = MUSIC_PALETTE[self._music_palette_index]
            self._music_palette_index = (self._music_palette_index + 1) % len(
                MUSIC_PALETTE
            )
        r, g, b = (round(c * amplitude / 100) for c in base_rgb)
        await self.stream_music_frame(r, g, b)

    # ---- state re-assertion ----

    async def _assert_look(self) -> None:
        """Re-send the current look (effect/scene/color) without power frames."""
        if self.state.effect_id is not None:
            await self._send(protocol.mode(self.state.effect_id))
        elif self.state.scene_id is not None:
            await self._send(protocol.scene(self.state.scene_id))
        else:
            await self._send(protocol.rgb(*self.state.rgb))

    async def restore_state(self) -> None:
        """Re-assert the full optimistic state (e.g. after music streaming
        or a reconnect): power, then look + brightness if on."""
        if not self.state.power:
            await self._send(protocol.power(False))
            return
        await self._send(protocol.power(True))
        await self._assert_look()
        percent = max(1, round(self.state.brightness * 100 / 255))
        await self._send(protocol.brightness(percent, 0))

    # ---- device configuration (expert; values persist in lamp NVRAM) ----

    async def set_symphony_point(self, count: int) -> None:
        """Set the addressable pixel count. MUST equal the physical LED count
        (80 on MELK-OC21); smaller values truncate the strip."""
        await self._send(protocol.symphony(count))

    async def set_pin_sequence(self, b2: int, b1: int, b0: int) -> None:
        """Remap RGB wire order. Do NOT send unless deliberately re-wiring."""
        await self._send(protocol.pin_sequence(b2, b1, b0))
