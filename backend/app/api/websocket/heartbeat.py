"""Server-driven heartbeat and stale connection cleanup (SOCKET_EVENTS.md §3)."""

from __future__ import annotations

import asyncio
import logging
import time

from app.api.websocket.connection_manager import ConnectionManager, connection_manager
from app.api.websocket.events import ServerEventType

logger = logging.getLogger(__name__)

# Defaults match SOCKET_EVENTS.md ("every 30s"). Tests may monkeypatch these.
HEARTBEAT_INTERVAL_SECONDS = 30.0
HEARTBEAT_TIMEOUT_SECONDS = 90.0


class HeartbeatMonitor:
    """Periodically ping clients and drop sockets that miss pong responses."""

    def __init__(
        self,
        manager: ConnectionManager | None = None,
        *,
        interval_seconds: float | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._manager = manager or connection_manager
        self.interval_seconds = (
            HEARTBEAT_INTERVAL_SECONDS if interval_seconds is None else interval_seconds
        )
        self.timeout_seconds = (
            HEARTBEAT_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
        )
        self._task: asyncio.Task | None = None
        self._stopped: asyncio.Event | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopped = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="ws-heartbeat")

    async def stop(self) -> None:
        if self._task is None:
            return
        if self._stopped is not None:
            self._stopped.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        self._stopped = None

    async def _run(self) -> None:
        assert self._stopped is not None
        while not self._stopped.is_set():
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self.interval_seconds)
                break
            except TimeoutError:
                await self.tick()

    async def tick(self) -> None:
        now = time.monotonic()
        stale: list = []
        for conn in self._manager.iter_all_connections():
            if now - conn.last_pong_at > self.timeout_seconds:
                stale.append(conn)
                continue
            await self._manager.send_to_connection(
                conn,
                ServerEventType.PING,
                {"serverTime": time.time()},
            )
        for conn in stale:
            logger.info(
                "Removing stale WebSocket connection",
                extra={"connection_id": conn.connection_id, "room_id": str(conn.room_id)},
            )
            await self._manager.close_connection(
                conn,
                code=4001,
                reason="Heartbeat timeout",
            )


heartbeat_monitor = HeartbeatMonitor()
