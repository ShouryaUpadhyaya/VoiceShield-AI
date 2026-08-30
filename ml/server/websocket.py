"""
WebSocket connection handler for the ML service.

Protocol per connection:
  1. Gateway opens WebSocket
  2. Gateway sends text frame (JSON metadata)
  3. Gateway sends binary frame (PCM16 audio)
  4. ML runs inference, sends JSON score response
  5. Repeat steps 2–4 for each chunk
  6. Connection closes when session ends or on disconnect

Multiple concurrent sessions (each with their own WebSocket connection) are
handled independently. Session state is per-connection, not global.

Bounded queue:
  Each connection has a max queue of MAX_PENDING_CHUNKS. If inference falls
  behind and the queue fills, dropped chunks are logged.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from typing import Deque

from fastapi import WebSocket, WebSocketDisconnect

from ml.server.protocol import ChunkMetadata, ProtocolError, parse_metadata, validate_audio_payload
from ml.pipeline.audio import AudioDecodeError, decode_gateway_chunk
from ml.pipeline.inference import run_inference
from ml.pipeline.results import build_score_response, build_error_response

logger = logging.getLogger(__name__)

# Max chunks to queue per connection before dropping
MAX_PENDING_CHUNKS = 10


class ConnectionState:
    """Per-connection state machine."""

    WAIT_METADATA = "WAIT_METADATA"
    WAIT_AUDIO    = "WAIT_AUDIO"

    def __init__(self, remote: str):
        self.remote = remote
        self.state = self.WAIT_METADATA
        self.pending_meta: ChunkMetadata | None = None
        self.chunks_received = 0
        self.chunks_processed = 0
        self.queue: Deque[dict] = deque(maxlen=MAX_PENDING_CHUNKS)
        self.connected_at = time.time()


async def handle_connection(websocket: WebSocket) -> None:
    """
    Handle one WebSocket connection from the Media Gateway.
    Runs until the connection closes or an unrecoverable error occurs.
    """
    await websocket.accept()
    remote = str(websocket.client) if websocket.client else "unknown"
    conn = ConnectionState(remote)

    logger.info("ML_CONNECTION", extra={"remote": remote})

    try:
        while True:
            # Receive the next frame (text or binary)
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                break

            msg_type = message.get("type")

            # ── Handle disconnect notification ────────────────────────
            if msg_type == "websocket.disconnect":
                break

            # ── Text frame → metadata ─────────────────────────────────
            if "text" in message and message["text"] is not None:
                await _handle_text_frame(websocket, conn, message["text"])
                continue

            # ── Binary frame → audio ──────────────────────────────────
            if "bytes" in message and message["bytes"] is not None:
                await _handle_binary_frame(websocket, conn, bytes(message["bytes"]))
                continue

    except Exception as exc:
        logger.error("ML_CONNECTION_ERROR", extra={"remote": remote, "error": str(exc)}, exc_info=True)
    finally:
        uptime = round(time.time() - conn.connected_at, 1)
        logger.info(
            "ML_DISCONNECT",
            extra={
                "remote": remote,
                "chunks_received": conn.chunks_received,
                "chunks_processed": conn.chunks_processed,
                "uptime_s": uptime,
            },
        )


async def _handle_text_frame(
    websocket: WebSocket,
    conn: ConnectionState,
    text: str,
) -> None:
    """Process a text frame — expected to be JSON chunk metadata."""

    if conn.state != ConnectionState.WAIT_METADATA:
        # Received metadata when we expected binary — log and reset
        logger.warning(
            "PROTOCOL_UNEXPECTED_TEXT",
            extra={"remote": conn.remote, "state": conn.state},
        )
        conn.state = ConnectionState.WAIT_METADATA
        conn.pending_meta = None

    try:
        meta = parse_metadata(text)
        conn.pending_meta = meta
        conn.state = ConnectionState.WAIT_AUDIO
        logger.debug(
            "CHUNK_METADATA_RECEIVED",
            extra={"session": meta.session_id, "sequence": meta.sequence},
        )
    except ProtocolError as exc:
        logger.warning("PROTOCOL_ERROR", extra={"code": exc.code, "message": str(exc)})
        error_resp = {
            "type": "ml.error",
            "error": {"code": exc.code, "message": str(exc)},
        }
        await websocket.send_text(json.dumps(error_resp))
        conn.state = ConnectionState.WAIT_METADATA
        conn.pending_meta = None


async def _handle_binary_frame(
    websocket: WebSocket,
    conn: ConnectionState,
    data: bytes,
) -> None:
    """Process a binary frame — expected to be PCM16 audio payload."""

    if conn.state != ConnectionState.WAIT_AUDIO or conn.pending_meta is None:
        logger.warning(
            "PROTOCOL_UNEXPECTED_BINARY",
            extra={"remote": conn.remote, "state": conn.state, "bytes": len(data)},
        )
        conn.state = ConnectionState.WAIT_METADATA
        conn.pending_meta = None
        return

    meta = conn.pending_meta
    conn.pending_meta = None
    conn.state = ConnectionState.WAIT_METADATA
    conn.chunks_received += 1

    logger.info(
        "CHUNK_RECEIVED",
        extra={
            "session": meta.session_id,
            "sequence": meta.sequence,
            "bytes": len(data),
            "duration_ms": meta.duration_ms,
        },
    )

    # Validate binary payload
    try:
        validate_audio_payload(meta, data)
    except ProtocolError as exc:
        logger.warning("PAYLOAD_VALIDATION_FAILED", extra={"code": exc.code, "message": str(exc)})
        err = build_error_response(meta.session_id, meta.sequence, exc.code, str(exc))
        await websocket.send_text(json.dumps(err))
        return

    # Run inference in a thread pool so we don't block the event loop
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            _infer_sync,
            meta,
            data,
        )
        conn.chunks_processed += 1
        await websocket.send_text(json.dumps(result))

    except AudioDecodeError as exc:
        logger.warning("AUDIO_DECODE_ERROR", extra={"error": str(exc)})
        err = build_error_response(meta.session_id, meta.sequence, "AUDIO_DECODE_ERROR", str(exc))
        await websocket.send_text(json.dumps(err))

    except Exception as exc:
        logger.error("INFERENCE_ERROR", extra={"error": str(exc)}, exc_info=True)
        # Do NOT expose stack trace to client
        err = build_error_response(
            meta.session_id, meta.sequence,
            "INFERENCE_FAILED",
            "Internal inference error. See ML service logs.",
        )
        await websocket.send_text(json.dumps(err))


def _infer_sync(meta: ChunkMetadata, pcm_bytes: bytes) -> dict:
    """
    Synchronous inference call — runs in thread pool executor.
    Decodes audio, runs all model adapters, builds response.
    """
    logger.info("INFERENCE_START", extra={"session": meta.session_id, "sequence": meta.sequence})

    # Decode and resample PCM16 → float32 @ 16 kHz
    audio_16k = decode_gateway_chunk(
        pcm_bytes,
        src_sr=meta.sample_rate,
    )

    # Run all adapters
    inference_result = run_inference(audio_16k, meta.session_id, meta.sequence)

    # Build gateway-compatible response
    score = build_score_response(
        session_id=meta.session_id,
        sequence=meta.sequence,
        timestamp_ms=meta.timestamp_ms,
        inference_result=inference_result,
    )

    return score
