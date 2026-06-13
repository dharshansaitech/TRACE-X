# backend/api/routes/websocket.py
from __future__ import annotations

import asyncio
import time

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from api.config import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter()
settings = get_settings()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    channels: str = Query(default="traces,failures,repairs"),
) -> None:
    """
    Main WebSocket endpoint for real-time updates.

    Query params:
    - channels: comma-separated list of channels to subscribe to
      Options: traces, agents, failures, repairs, agent:{id}, trace:{id}

    Message types from server:
    - connected: initial connection acknowledgment
    - new_trace: a new trace was ingested
    - failure_detected: observer detected a failure
    - diagnosis_complete: diagnosis finished
    - repair_generated: new repair available
    - repair_applied: repair was applied
    - pong: response to client ping
    - subscribed/unsubscribed: channel subscription changes

    Message types from client:
    - ping: keepalive
    - subscribe: {"type": "subscribe", "channels": ["traces"]}
    - unsubscribe: {"type": "unsubscribe", "channels": ["traces"]}
    """
    ws_manager = websocket.app.state.ws_manager

    # Parse requested channels
    requested_channels = [c.strip() for c in channels.split(",") if c.strip()]

    # Connect
    connection_id = await ws_manager.connect(websocket, requested_channels)

    # Heartbeat task
    async def send_heartbeat():
        while True:
            await asyncio.sleep(settings.ws_heartbeat_interval_seconds)
            conn = ws_manager.connections.get(connection_id)
            if not conn:
                break
            success = await ws_manager.send_to_connection(
                connection_id,
                {"type": "heartbeat", "timestamp": time.time()},
            )
            if not success:
                break

    heartbeat_task = asyncio.create_task(send_heartbeat())

    try:
        while True:
            # Wait for incoming message
            data = await websocket.receive_text()
            await ws_manager.handle_incoming(connection_id, data)

    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", connection_id=connection_id)
    except Exception as exc:
        logger.warning("ws_error", connection_id=connection_id, error=str(exc))
    finally:
        heartbeat_task.cancel()
        await ws_manager.disconnect(connection_id)
