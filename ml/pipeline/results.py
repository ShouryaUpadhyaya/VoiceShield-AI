"""
Result builder — converts raw inference output into the `type:score` response
shape that the Media Gateway `ml-client.ts` and `persistence.ts` expect.

Gateway expects (from ml-client.ts line 81):
  msg.type === 'score'
  msg.metadata?.session_id
  msg.window_seq
  persistMlResult(msg.metadata.session_id, msg.window_seq, msg)

persistence.ts reads:
  result.backend              → model_name
  result.inference_ms         → latency_ms
  result.signals.deepfake_probability
  result.signals.speaker_match.speaker_id
  result.signals.prosody_analysis.overall_prosody_risk
"""
from __future__ import annotations

import time
from typing import Any

from ml.common.constants import ML_SERVICE_VERSION, GATEWAY_SAMPLE_RATE, SAMPLE_RATE


def build_score_response(
    session_id: str,
    sequence: int,
    timestamp_ms: int,
    inference_result: dict,
) -> dict:
    """
    Build the complete `type:score` JSON to send back to the Media Gateway.

    Parameters
    ----------
    session_id : str
    sequence : int
    timestamp_ms : int
        Chunk start timestamp in ms (from gateway metadata).
    inference_result : dict
        Output from pipeline.inference.run_inference().

    Returns
    -------
    dict
        Gateway-compatible score response.
    """

    dhwani = inference_result.get("dhwani")
    deepfake = inference_result.get("custom_deepfake")
    prosody = inference_result.get("prosody")
    speaker = inference_result.get("speaker_verification")

    # ── Compute unified deepfake_probability ──────────────────────────
    # Priority: Dhwani (primary), then custom deepfake as fallback.
    # Both are "synthetic probability" (0 = genuine, 1 = synthetic/fake).
    deepfake_probability = None

    if dhwani is not None:
        deepfake_probability = dhwani["synthetic_probability"]
    elif deepfake is not None:
        deepfake_probability = deepfake["deepfake_probability"]

    # ── Build signals sub-document ────────────────────────────────────
    signals: dict[str, Any] = {
        "deepfake_probability": deepfake_probability,

        "dhwani": dhwani,

        "custom_deepfake": deepfake,

        "prosody_analysis": prosody,  # includes overall_prosody_risk

        "speaker_match": speaker,     # includes speaker_id for persistence
    }

    # ── Model versions ────────────────────────────────────────────────
    from ml.adapters import dhwani as da
    from ml.adapters import deepfake as dfa
    from ml.adapters import speaker as sa
    from ml.adapters import prosody as pa

    model_versions = {
        "dhwani":           da.get_version(),
        "custom_deepfake":  dfa.get_version(),
        "speaker":          sa.get_version(),
        "prosody":          pa.get_version(),
    }

    return {
        # ── Gateway protocol fields ───────────────────────────────────
        "type":       "score",
        "window_seq": sequence,

        "metadata": {
            "session_id": session_id,
            "sequence":   sequence,
        },

        # ── VoiceShield ML identity ───────────────────────────────────
        "backend":      ML_SERVICE_VERSION,
        "schema_version": 1,

        # ── Audio context ─────────────────────────────────────────────
        "audio": {
            "input_sample_rate":  GATEWAY_SAMPLE_RATE,
            "model_sample_rate":  SAMPLE_RATE,
            "channels":           1,
            "duration_ms":        round(inference_result.get("audio_duration_ms", 3000)),
            "timestamp_ms":       timestamp_ms,
        },

        # ── Inference timing ──────────────────────────────────────────
        "inference_ms":      round(inference_result["total_latency_ms"]),
        "real_time_factor":  inference_result["real_time_factor"],

        # ── ML signals (what persistence.ts reads) ────────────────────
        "signals": signals,

        # ── Model metadata ────────────────────────────────────────────
        "model_versions": model_versions,
        "models_available": inference_result.get("models_available", {}),
        "model_errors":     inference_result.get("model_errors", {}),
    }


def build_error_response(
    session_id: str,
    sequence: int,
    error_code: str,
    error_message: str,
) -> dict:
    """
    Build an error response for a chunk that could not be processed.
    Does NOT expose Python stack traces.
    """
    return {
        "type":       "ml.error",
        "window_seq": sequence,
        "metadata": {
            "session_id": session_id,
            "sequence":   sequence,
        },
        "error": {
            "code":    error_code,
            "message": error_message,
        },
    }
