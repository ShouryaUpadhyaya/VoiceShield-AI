"""
Inference orchestrator — runs all model adapters sequentially for one chunk.

Design:
  - Each model runs in isolation: failure of one does NOT abort the others
  - Per-model timing is captured
  - Results are collected even if some models are unavailable
  - Total latency = wall-clock time across all models

Model failure isolation example:
  Dhwani:  SUCCESS → included in result
  Prosody: SUCCESS → included in result
  Speaker: EXCEPTION → error recorded, other results returned normally
"""
from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np

from ml.adapters import dhwani as dhwani_adapter
from ml.adapters import deepfake as deepfake_adapter
from ml.adapters import speaker as speaker_adapter
from ml.adapters import prosody as prosody_adapter
from ml.adapters import indic as indic_adapter

logger = logging.getLogger(__name__)


def _run_isolated(name: str, fn, *args, **kwargs) -> tuple[Any, str | None]:
    """
    Call fn(*args, **kwargs), catching all exceptions.

    Returns (result, error_str). On success error_str is None.
    On failure result is None and error_str contains the exception message.
    """
    try:
        result = fn(*args, **kwargs)
        return result, None
    except Exception as exc:
        logger.error(
            "MODEL_ERROR",
            extra={"model": name, "error": str(exc)},
            exc_info=True,
        )
        return None, str(exc)


def run_inference(
    audio_16k: np.ndarray,
    session_id: str,
    sequence: int,
) -> dict:
    """
    Run all model adapters against one 3-second 16 kHz float32 chunk.

    Parameters
    ----------
    audio_16k : np.ndarray
        Shape (48000,) float32, 16 kHz, mono.
    session_id : str
        Session identifier from the gateway metadata.
    sequence : int
        Chunk sequence number from the gateway metadata.

    Returns
    -------
    dict with keys:
        total_latency_ms, real_time_factor,
        dhwani, custom_deepfake, prosody, speaker_verification,
        model_errors, models_available
    """
    wall_start = time.perf_counter()

    audio_duration_ms = len(audio_16k) / 16000.0 * 1000.0  # should be ~3000

    logger.info(
        "INFERENCE_START",
        extra={"session": session_id, "sequence": sequence, "samples": len(audio_16k)},
    )

    # ------------------------------------------------------------------ #
    # Run each model in isolation
    # ------------------------------------------------------------------ #

    dhwani_result, dhwani_error = _run_isolated(
        "dhwani", dhwani_adapter.run, audio_16k
    )

    deepfake_result, deepfake_error = _run_isolated(
        "custom_deepfake", deepfake_adapter.run, audio_16k
    )

    prosody_result, prosody_error = _run_isolated(
        "prosody", prosody_adapter.run, audio_16k
    )

    indic_result, indic_error = _run_isolated(
        "indic", indic_adapter.run, audio_16k
    )

    speaker_result, speaker_error = _run_isolated(
        "speaker", speaker_adapter.run, audio_16k
    )

    # ------------------------------------------------------------------ #
    # Aggregate timing and metadata
    # ------------------------------------------------------------------ #

    total_latency_ms = (time.perf_counter() - wall_start) * 1000.0
    real_time_factor = total_latency_ms / audio_duration_ms if audio_duration_ms > 0 else 0.0

    model_errors: dict[str, str] = {}
    if dhwani_error:
        model_errors["dhwani"] = dhwani_error
    if deepfake_error:
        model_errors["custom_deepfake"] = deepfake_error
    if prosody_error:
        model_errors["prosody"] = prosody_error
    if indic_error:
        model_errors["indic"] = indic_error
    if speaker_error:
        model_errors["speaker"] = speaker_error

    models_available = {
        "dhwani":           dhwani_adapter.is_loaded(),
        "custom_deepfake":  deepfake_adapter.is_loaded(),
        "prosody":          prosody_adapter.is_loaded(),
        "indic":            indic_adapter.is_loaded(),
        "speaker":          speaker_adapter.is_loaded(),
    }

    logger.info(
        "INFERENCE_COMPLETE",
        extra={
            "session": session_id,
            "sequence": sequence,
            "latency_ms": round(total_latency_ms, 1),
            "real_time_factor": round(real_time_factor, 3),
            "errors": list(model_errors.keys()),
        },
    )

    return {
        "total_latency_ms":     round(total_latency_ms, 2),
        "real_time_factor":     round(real_time_factor, 4),
        "audio_duration_ms":    round(audio_duration_ms, 1),
        "dhwani":               dhwani_result,
        "custom_deepfake":      deepfake_result,
        "prosody":              prosody_result,
        "indic":                indic_result,
        "speaker_verification": speaker_result,
        "model_errors":         model_errors,
        "models_available":     models_available,
    }
