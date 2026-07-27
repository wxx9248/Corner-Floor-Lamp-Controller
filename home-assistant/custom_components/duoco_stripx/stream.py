"""UDP ingest for music-amplitude streaming (WLED-style realtime path).

The lamp pulses to a ~10 Hz stream of music frames over BLE, but accepts only
one BLE connection — so Home Assistant keeps the connection and proxies:
an external audio pipeline sends tiny UDP packets here and they are forwarded
as `[7]=0x20` music frames.

The lamp does no audio processing of its own, so all of it — amplitude
detection, color choice, brightness scaling — is the client's job. HA is a
dumb relay: exactly 3 bytes, `[R, G, B]`, forwarded as-is. Anything else is
ignored.

Behavior:
- forwarding is rate-limited (latest packet wins between BLE writes)
- a 5 s silence watchdog auto-disarms and restores the pre-streaming state,
  so an abandoned streamer never leaves the lamp frozen dark.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

from duoco_stripx import DuocoStripXDevice

_LOGGER = logging.getLogger(__name__)

FORWARD_INTERVAL = 0.05  # min seconds between forwarded BLE frames
WATCHDOG_TIMEOUT = 5.0  # seconds without packets before auto-disarm


class MusicStreamer(asyncio.DatagramProtocol):
    """Arms a UDP listener and forwards packets as BLE music frames."""

    def __init__(self, device: DuocoStripXDevice, port: int) -> None:
        self._device = device
        self._port = port
        self._transport: asyncio.DatagramTransport | None = None
        self._task: asyncio.Task | None = None
        self._pending: tuple[int, int, int] | None = None
        self._last_rx = 0.0
        # notified with the new active state on start/stop (incl. watchdog)
        self._state_callbacks: list[Callable[[bool], None]] = []

    @property
    def active(self) -> bool:
        return self._transport is not None

    @property
    def port(self) -> int:
        return self._port

    def register_state_callback(
        self, callback: Callable[[bool], None]
    ) -> Callable[[], None]:
        self._state_callbacks.append(callback)

        def unregister() -> None:
            self._state_callbacks.remove(callback)

        return unregister

    def _notify(self) -> None:
        for callback in self._state_callbacks:
            callback(self.active)

    # ---- lifecycle ----

    async def start(self) -> None:
        if self.active:
            return
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: self, local_addr=("0.0.0.0", self._port)
        )
        self._pending = None
        self._last_rx = time.monotonic()
        self._task = loop.create_task(self._forward_loop())
        _LOGGER.debug("music streaming armed on udp/%d", self._port)
        self._notify()

    async def stop(self, restore: bool = True) -> None:
        if not self.active:
            return
        assert self._transport is not None
        self._transport.close()
        self._transport = None
        if self._task is not None:
            self._task.cancel()
            self._task = None
        if restore:
            # un-freeze the lamp from the last music frame
            await self._device.restore_state()
        _LOGGER.debug("music streaming disarmed")
        self._notify()

    # ---- datagram protocol ----

    def datagram_received(self, data: bytes, _addr: tuple) -> None:
        if len(data) != 3:
            return
        self._pending = (data[0], data[1], data[2])
        self._last_rx = time.monotonic()

    def error_received(self, exc: Exception) -> None:
        _LOGGER.debug("UDP error: %s", exc)

    # ---- forwarding + watchdog ----

    async def _forward_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(FORWARD_INTERVAL)
                if time.monotonic() - self._last_rx > WATCHDOG_TIMEOUT:
                    _LOGGER.info(
                        "no music packets for %.0f s — auto-disarming",
                        WATCHDOG_TIMEOUT,
                    )
                    asyncio.get_running_loop().create_task(self.stop())
                    return
                pending, self._pending = self._pending, None
                if pending is not None:
                    try:
                        await self._device.stream_music_frame(*pending)
                    except Exception:  # noqa: BLE001 — keep the stream alive
                        _LOGGER.warning("music frame write failed", exc_info=True)
        except asyncio.CancelledError:
            pass
