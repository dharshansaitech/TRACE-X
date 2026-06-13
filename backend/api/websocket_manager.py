# backend/api/websocket_manager.py
from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger(__name__)


@dataclass
class WebSocketConnection:
    """Represents a single WebSocket connection with metadata."""
    connection_id: str
    websocket: WebSocket
    channels: set[str] = field(default_factory=set)
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    message_count: int = 0


class WebSocketManager:
    """
    Manages WebSocket connections with channel-based subscriptions.

    Clients can subscribe to channels like:
    - "traces" — new traces
    - "agents" — agent status updates
    - "failures" — failure events
    - "repairs" — repair events
    - "agent:{agent_id}" — specific agent events
    - "trace:{trace_id}" — specific trace events
    """

    def __init__(self) -> None:
        self.connections: dict[str, WebSocketConnection] = {}
        self._channel_subscribers: defaultdict[str, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, channels: list[str] | None = None) -> str:
        """Accept a WebSocket connection and register it."""
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        conn = WebSocketConnection(
            connection_id=connection_id,
            websocket=websocket,
            channels=set(channels or ["traces", "failures", "repairs"]),
        )

        async with self._lock:
            self.connections[connection_id] = conn
            for channel in conn.channels:
                self._channel_subscribers[channel].add(connection_id)

        logger.info(
            "ws_connected",
            connection_id=connection_id,
            channels=list(conn.channels),
            total_connections=len(self.connections),
        )

        # Send welcome message
        await self._send_to_connection(
            connection_id,
            {
                "type": "connected",
                "connection_id": connection_id,
                "channels": list(conn.channels),
                "timestamp": time.time(),
            },
        )
        return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """Remove a connection and clean up subscriptions."""
        async with self._lock:
            conn = self.connections.pop(connection_id, None)
            if conn:
                for channel in conn.channels:
                    self._channel_subscribers[channel].discard(connection_id)

        logger.info(
            "ws_disconnected",
            connection_id=connection_id,
            total_connections=len(self.connections),
        )

    async def subscribe(self, connection_id: str, channels: list[str]) -> None:
        """Add a connection to additional channels."""
        async with self._lock:
            conn = self.connections.get(connection_id)
            if not conn:
                return
            for channel in channels:
                conn.channels.add(channel)
                self._channel_subscribers[channel].add(connection_id)

    async def unsubscribe(self, connection_id: str, channels: list[str]) -> None:
        """Remove a connection from channels."""
        async with self._lock:
            conn = self.connections.get(connection_id)
            if not conn:
                return
            for channel in channels:
                conn.channels.discard(channel)
                self._channel_subscribers[channel].discard(connection_id)

    async def broadcast_to_channel(self, channel: str, message: dict[str, Any]) -> int:
        """Broadcast a message to all subscribers of a channel."""
        subscriber_ids = list(self._channel_subscribers.get(channel, set()))
        if not subscriber_ids:
            return 0

        sent = 0
        failed: list[str] = []

        for connection_id in subscriber_ids:
            success = await self._send_to_connection(connection_id, message)
            if success:
                sent += 1
            else:
                failed.append(connection_id)

        # Clean up failed connections
        for connection_id in failed:
            await self.disconnect(connection_id)

        return sent

    async def broadcast_to_all(self, message: dict[str, Any]) -> int:
        """Broadcast a message to all connected clients."""
        connection_ids = list(self.connections.keys())
        sent = 0
        failed: list[str] = []

        for connection_id in connection_ids:
            success = await self._send_to_connection(connection_id, message)
            if success:
                sent += 1
            else:
                failed.append(connection_id)

        for connection_id in failed:
            await self.disconnect(connection_id)

        return sent

    async def send_to_connection(self, connection_id: str, message: dict[str, Any]) -> bool:
        """Send a message to a specific connection."""
        return await self._send_to_connection(connection_id, message)

    async def _send_to_connection(self, connection_id: str, message: dict[str, Any]) -> bool:
        """Internal: send message to a specific connection."""
        conn = self.connections.get(connection_id)
        if not conn:
            return False

        try:
            await conn.websocket.send_text(json.dumps(message, default=str))
            conn.message_count += 1
            return True
        except Exception as exc:
            logger.warning(
                "ws_send_failed",
                connection_id=connection_id,
                error=str(exc),
            )
            return False

    async def handle_incoming(self, connection_id: str, data: str) -> None:
        """Handle incoming message from client."""
        try:
            msg = json.loads(data)
            msg_type = msg.get("type", "unknown")

            if msg_type == "ping":
                conn = self.connections.get(connection_id)
                if conn:
                    conn.last_ping = time.time()
                await self._send_to_connection(
                    connection_id, {"type": "pong", "timestamp": time.time()}
                )

            elif msg_type == "subscribe":
                channels = msg.get("channels", [])
                await self.subscribe(connection_id, channels)
                await self._send_to_connection(
                    connection_id,
                    {
                        "type": "subscribed",
                        "channels": channels,
                        "timestamp": time.time(),
                    },
                )

            elif msg_type == "unsubscribe":
                channels = msg.get("channels", [])
                await self.unsubscribe(connection_id, channels)
                await self._send_to_connection(
                    connection_id,
                    {
                        "type": "unsubscribed",
                        "channels": channels,
                        "timestamp": time.time(),
                    },
                )

            else:
                logger.debug(
                    "ws_unknown_message_type",
                    connection_id=connection_id,
                    msg_type=msg_type,
                )

        except json.JSONDecodeError:
            logger.warning("ws_invalid_json", connection_id=connection_id)

    async def close_all(self) -> None:
        """Close all WebSocket connections on shutdown."""
        connection_ids = list(self.connections.keys())
        for connection_id in connection_ids:
            conn = self.connections.get(connection_id)
            if conn:
                try:
                    await conn.websocket.close()
                except Exception:
                    pass
        self.connections.clear()
        self._channel_subscribers.clear()
        logger.info("ws_all_connections_closed")

    @property
    def connection_count(self) -> int:
        return len(self.connections)

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_connections": len(self.connections),
            "channels": {
                channel: len(subs)
                for channel, subs in self._channel_subscribers.items()
            },
        }
