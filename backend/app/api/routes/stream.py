"""WebSocket streaming analysis.

A minimal streaming bridge: it maintains a per-connection rolling PCM buffer,
emits a fixed-length analysis window every hop, and streams a scored result
back for each one. This is the prototype-scale version of the component
specified in docs/streaming_bridge/ — enough to demonstrate the real workflow,
not yet the production article.

TWO RULES THIS FILE EXISTS TO ENFORCE
-------------------------------------
1. A missing score is NEVER reported as a low score. If the detector is
   unavailable we emit status=DETECTOR_UNAVAILABLE and no risk number at all.
   Substituting 0.0 would tell the risk engine "definitely genuine" and
   green-light the exact fraud this system exists to stop.

2. The model is fed the window length it was TRAINED on, not whatever chunk
   size the client happens to send. A 100 ms chunk scored by a model trained on
   3 s windows is a train/serve mismatch that silently degrades every score.

PROTOCOL
--------
client -> server : binary PCM frames (16 kHz mono float32 or int16), or a
                   JSON control message {"type":"config"|"eof"}
server -> client : one JSON RiskScoreUpdate per completed window
"""

from __future__ import annotations

import json
import logging
import time

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.deepfake_service import analyze_deepfake_window, backend_name, get_predictor
from app.services.prevention_service import trigger_prevention
from app.services.prosody_service import analyze_prosody
from app.services.risk_service import calculate_risk
from app.services.speaker_service import verify_speaker

router = APIRouter()
logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
HOP_SAMPLES = int(0.5 * SAMPLE_RATE)      # emit a score every 500 ms
MAX_BUFFER = 30 * SAMPLE_RATE             # hard cap: never grow without bound


def _window_samples() -> int:
    """Window length comes from the loaded model, never from a constant here.

    Two backends expose it differently — Dhwani as `window_samples`, the fusion
    predictor as `front_end.segment_samples` (read from its checkpoint). Getting
    this wrong is silent: the model simply receives a duration it was not
    trained on and every score degrades without any error.
    """
    d = get_predictor()
    if d is None:
        return 3 * SAMPLE_RATE
    n = getattr(d, "window_samples", None)
    if not n:
        fe = getattr(d, "front_end", None)
        n = getattr(fe, "segment_samples", None) if fe is not None else None
    return int(n or 3 * SAMPLE_RATE)


def _to_float32(raw: bytes) -> np.ndarray:
    """Accept float32 or int16 PCM; int16 is what most telephony stacks emit."""
    if len(raw) % 4 == 0:
        f = np.frombuffer(raw, dtype="<f4")
        if f.size and np.isfinite(f).all() and np.abs(f).max() <= 1.5:
            return f.astype(np.float32, copy=True)
    if len(raw) % 2 == 0:
        return (np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0)
    return np.frombuffer(raw[: len(raw) // 2 * 2], dtype="<i2").astype(np.float32) / 32768.0


@router.websocket("/analyze-stream")
async def websocket_analyze_stream(websocket: WebSocket):
    await websocket.accept()
    
    call_metadata = {}
    for key, value in websocket.headers.items():
        if key.startswith("x-"):
            call_metadata[key] = value

    win = _window_samples()
    buf = np.zeros(0, dtype=np.float32)
    sample_offset = 0          # authoritative clock — cumulative samples, not wall time
    window_seq = 0
    logger.info("stream open · backend=%s · window=%.1fs · hop=%.1fs",
                backend_name(), win / SAMPLE_RATE, HOP_SAMPLES / SAMPLE_RATE)

    await websocket.send_json({
        "type": "session_open",
        "backend": backend_name(),
        "window_seconds": round(win / SAMPLE_RATE, 2),
        "hop_seconds": round(HOP_SAMPLES / SAMPLE_RATE, 2),
        "sample_rate": SAMPLE_RATE,
    })

    try:
        while True:
            msg = await websocket.receive()

            if msg.get("type") == "websocket.disconnect":
                break

            if msg.get("text") is not None:
                try:
                    ctl = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue
                if ctl.get("type") == "eof":
                    # Flush whatever is left as one final (partial) window.
                    if buf.size >= SAMPLE_RATE // 2:
                        pad = np.tile(buf, int(np.ceil(win / buf.size)))[:win]
                        await _emit(websocket, pad, window_seq, sample_offset, partial=True, call_metadata=call_metadata)
                    await websocket.send_json({"type": "session_closed", "windows": window_seq})
                    break
                else:
                    call_metadata.update(ctl)
                continue

            raw = msg.get("bytes")
            if not raw:
                continue

            buf = np.concatenate([buf, _to_float32(raw)])
            if buf.size > MAX_BUFFER:                     # drop OLDEST, never block
                dropped = buf.size - MAX_BUFFER
                buf = buf[dropped:]
                sample_offset += dropped
                logger.warning("buffer overflow, dropped %d oldest samples", dropped)

            # Emit every complete window the buffer now contains.
            while buf.size >= win:
                await _emit(websocket, buf[:win], window_seq, sample_offset, call_metadata=call_metadata)
                window_seq += 1
                buf = buf[HOP_SAMPLES:]
                sample_offset += HOP_SAMPLES

    except WebSocketDisconnect:
        logger.info("client disconnected after %d windows", window_seq)
    except Exception:
        logger.exception("stream error")
        try:
            await websocket.send_json({"type": "error", "status": "STREAM_ERROR"})
        except Exception:
            pass


async def _emit(ws: WebSocket, window: np.ndarray, seq: int, offset: int, partial: bool = False, call_metadata: dict = None):
    t0 = time.perf_counter()

    try:
        # Pass decoded PCM straight to the model — no encode/decode round-trip.
        deepfake = analyze_deepfake_window(window)
    except ValueError as exc:
        await ws.send_json({"type": "score", "window_seq": seq, "status": "DECODE_ERROR",
                            "detail": str(exc)})
        return

    # RULE 1 — a detector that cannot answer must say so, not answer zero.
    if not deepfake.get("available") and not deepfake.get("demo_mode"):
        await ws.send_json({
            "type": "score", "window_seq": seq, "sample_offset": offset,
            "status": "DETECTOR_UNAVAILABLE",
            "risk_assessment": None,
            "note": "no score produced — absence of a score is not a low score",
        })
        return

    prob = deepfake["deepfake_probability"]
    speaker = verify_speaker("stream.wav", b"")
    prosody = analyze_prosody("stream.wav", b"")
    risk = calculate_risk(deepfake_prob=prob, speaker_match=speaker,
                          prosody_anomaly=prosody["overall_prosody_risk"], context_risk=0.5)
    prevention = trigger_prevention(risk["risk_score"], risk["risk_level"])

    await ws.send_json({
        "type": "score",
        "window_seq": seq,
        "sample_offset": offset,
        "audio_time_s": round(offset / SAMPLE_RATE, 2),
        "partial": partial,
        "status": "DEMO_MODE" if deepfake.get("demo_mode") else "OK",
        "backend": deepfake.get("model"),
        "validated": deepfake.get("validated", False),
        "warning": deepfake.get("warning"),
        "signals": {
            "deepfake_probability": prob,
            "speaker_match": speaker,
            "prosody_analysis": prosody,
            "context_risk": 0.5,
        },
        "signal_provenance": {
            "deepfake_probability": "model" if deepfake.get("available") else "placeholder",
            "speaker_match": "placeholder",
            "prosody_analysis": "placeholder",
            "context_risk": "placeholder",
        },
        "risk_assessment": risk,
        "prevention_status": prevention,
        "inference_ms": round((time.perf_counter() - t0) * 1000, 1),
        "metadata": call_metadata or {},
    })
