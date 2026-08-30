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
import os


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
    indic = inference_result.get("indic")
    prosody = inference_result.get("prosody")
    speaker = inference_result.get("speaker_verification")

    # ── Weighted Fusion ───────────────────────────────────────────────
    raw_weights = {
        "indic": float(os.environ.get("FUSION_INDIC_WEIGHT", "0.45")),
        "dhwani": float(os.environ.get("FUSION_DHWANI_WEIGHT", "0.20")),
        "customDeepfake": float(os.environ.get("FUSION_CUSTOM_WEIGHT", "0.20")),
        "prosody": float(os.environ.get("FUSION_PROSODY_WEIGHT", "0.15"))
    }

    # Gather available scores and weights
    available_scores = {}
    available_weights = {}

    if indic is not None:
        available_scores["indic"] = indic["synthetic_probability"]
        available_weights["indic"] = raw_weights["indic"]
    if dhwani is not None:
        available_scores["dhwani"] = dhwani["synthetic_probability"]
        available_weights["dhwani"] = raw_weights["dhwani"]
    if deepfake is not None:
        available_scores["customDeepfake"] = deepfake["deepfake_probability"]
        available_weights["customDeepfake"] = raw_weights["customDeepfake"]
    if prosody is not None:
        available_scores["prosody"] = prosody.get("overall_prosody_risk", 0.0)
        available_weights["prosody"] = raw_weights["prosody"]

    total_available_weight = sum(available_weights.values())
    ai_generated_score = None
    fusion_details = None

    if total_available_weight > 0:
        normalized_weights = {k: v / total_available_weight for k, v in available_weights.items()}
        ai_generated_score = sum(available_scores[k] * normalized_weights[k] for k in available_scores)
        
        fusion_details = {
            "aiGeneratedScore": round(ai_generated_score, 4),
            "method": "weighted_mean",
            "weights": normalized_weights,
            "contributions": {
                k: round(available_scores[k] * normalized_weights[k], 4) for k in available_scores
            }
        }

    # ── Build detectors sub-document ──────────────────────────────────
    detectors_doc = {
        "indic": {
            "score": available_scores.get("indic"),
            "weight": available_weights.get("indic"),
            "status": "complete" if "indic" in available_scores else "unavailable"
        },
        "dhwani": {
            "score": available_scores.get("dhwani"),
            "weight": available_weights.get("dhwani"),
            "status": "complete" if "dhwani" in available_scores else "unavailable"
        },
        "customDeepfake": {
            "score": available_scores.get("customDeepfake"),
            "weight": available_weights.get("customDeepfake"),
            "status": "complete" if "customDeepfake" in available_scores else "unavailable"
        },
        "prosody": {
            "score": available_scores.get("prosody"),
            "weight": available_weights.get("prosody"),
            "status": "complete" if "prosody" in available_scores else "unavailable"
        }
    }

    # ── Build signals sub-document ────────────────────────────────────
    signals: dict[str, Any] = {
        "deepfake_probability": round(ai_generated_score, 4) if ai_generated_score is not None else None,

        "indic": indic,

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
    from ml.adapters import indic as ia

    model_versions = {
        "dhwani":           da.get_version(),
        "custom_deepfake":  dfa.get_version(),
        "indic":            ia.get_version(),
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
        
        # ── Weighted Fusion and Detectors (UI rendering) ──────────────
        "fusion": fusion_details,
        "detectors": detectors_doc,

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
