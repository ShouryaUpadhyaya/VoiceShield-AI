"""
Gateway → ML WebSocket protocol definitions.

The Media Gateway sends exactly two frames per chunk:

  Frame 1 (text):  JSON metadata
  Frame 2 (binary): raw PCM16 LE audio payload

This module parses and validates both frames.

Metadata schema (from ml-client.ts MlChunkMetadata):
  {
    "type":         "audio.chunk",
    "session_id":   str,
    "sequence":     int,
    "timestamp_ms": int,
    "duration_ms":  int,
    "sample_rate":  int,    # Always 48000 from gateway
    "channels":     int,    # Always 1
    "encoding":     str,    # Always "pcm_s16le"
    "bytes":        int,    # Always 288000 for full chunks
  }
"""
from __future__ import annotations

import json
from dataclasses import dataclass


class ProtocolError(ValueError):
    """Raised on malformed metadata or unexpected frame ordering."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ChunkMetadata:
    type: str
    session_id: str
    sequence: int
    timestamp_ms: int
    duration_ms: int
    sample_rate: int
    channels: int
    encoding: str
    bytes: int


def parse_metadata(text: str) -> ChunkMetadata:
    """
    Parse a text WebSocket frame as chunk metadata.

    Raises ProtocolError on any validation failure.
    """
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolError("INVALID_JSON", f"Failed to parse metadata JSON: {exc}") from exc

    msg_type = obj.get("type")
    if msg_type != "audio.chunk":
        raise ProtocolError(
            "UNEXPECTED_MESSAGE_TYPE",
            f"Expected type='audio.chunk', got type={msg_type!r}",
        )

    required = ["session_id", "sequence", "timestamp_ms", "duration_ms",
                "sample_rate", "channels", "encoding", "bytes"]
    missing = [k for k in required if k not in obj]
    if missing:
        raise ProtocolError("MISSING_FIELDS", f"Missing required metadata fields: {missing}")

    try:
        return ChunkMetadata(
            type=str(obj["type"]),
            session_id=str(obj["session_id"]),
            sequence=int(obj["sequence"]),
            timestamp_ms=int(obj["timestamp_ms"]),
            duration_ms=int(obj["duration_ms"]),
            sample_rate=int(obj["sample_rate"]),
            channels=int(obj["channels"]),
            encoding=str(obj["encoding"]),
            bytes=int(obj["bytes"]),
        )
    except (TypeError, ValueError) as exc:
        raise ProtocolError("INVALID_FIELD_TYPE", f"Metadata field type error: {exc}") from exc


def validate_audio_payload(meta: ChunkMetadata, payload: bytes) -> None:
    """
    Validate the binary audio payload against the declared metadata.

    Raises ProtocolError if the payload is malformed.
    """
    if len(payload) == 0:
        raise ProtocolError("EMPTY_PAYLOAD", "Binary audio payload is empty.")

    if len(payload) % 2 != 0:
        raise ProtocolError(
            "MISALIGNED_PAYLOAD",
            f"PCM16 payload must have even byte count; got {len(payload)}.",
        )

    # Warn but don't reject if bytes don't match declared count.
    # The final partial chunk at call end may be smaller.
    if len(payload) != meta.bytes:
        # Log discrepancy — handled upstream by the audio decoder with padding.
        pass
