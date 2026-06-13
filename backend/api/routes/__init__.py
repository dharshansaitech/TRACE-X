# backend/api/routes/__init__.py
from api.routes import agents, dashboard, diagnoses, repairs, replay, simulator, traces
from api.routes import websocket

__all__ = ["agents", "dashboard", "diagnoses", "repairs", "replay", "simulator", "traces", "websocket"]
