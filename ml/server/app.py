"""
FastAPI application factory for the VoiceShield ML service.

Routes:
  GET  /health     → Health check (process alive)
  GET  /ready      → Readiness check (models loaded)
  WS   /           → WebSocket audio chunk endpoint (gateway connects here)

The WebSocket endpoint is at the root path because the gateway connects to:
  ws://localhost:8011

Which resolves to ws://localhost:8011/
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from ml.server.health import health_router
from ml.server.api import api_router
from ml.server.websocket import handle_connection

logger = logging.getLogger(__name__)

app = FastAPI(
    title="VoiceShield ML Service",
    description="Real-time deepfake detection, prosody analysis, and speaker verification.",
    version="1.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount health/ready routes
app.include_router(health_router)
app.include_router(api_router)


@app.websocket("/")
async def ml_websocket(websocket: WebSocket):
    """
    Primary WebSocket endpoint.

    The Media Gateway connects here (ws://localhost:8011).
    One WebSocket connection per gateway session.
    Multiple concurrent connections are supported.
    """
    await handle_connection(websocket)
