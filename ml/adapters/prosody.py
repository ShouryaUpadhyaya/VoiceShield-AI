"""
Prosody adapter — combines all prosody modules into a single inference call.

Prosody functions use Parselmouth (Praat bindings) + librosa.
All functions accept (y: np.ndarray, sr: int) at 16 kHz.

Output structure:
  {
    # From extract_pitch_stats():
    "f0_mean":         float,  # Mean fundamental frequency (Hz)
    "f0_std":          float,  # Standard deviation of F0 (Hz) — pitch dynamism
    "f0_range":        float,  # F0 range max-min (Hz)
    "voiced_ratio":    float,  # Fraction of frames that are voiced

    # From extract_pause_stats():
    "pause_count":     int,    # Number of silent segments
    "mean_pause_ratio":float,  # Fraction of frames below silence threshold

    # From extract_voice_quality():
    "jitter":          float,  # Micro-pitch stability (lower = more stable)
    "shimmer":         float,  # Micro-amplitude stability
    "hnr":             float,  # Harmonics-to-noise ratio (dB)

    # From estimate_speaking_rate():
    "speaking_rate":   float,  # Estimated syllables/sec

    # From prosodic_anomaly_score():
    "anomaly_score":   float,  # 0–1; higher = more anomalous vs. natural speech
    "overall_prosody_risk": float,  # alias for anomaly_score (gateway compat)

    # Metadata
    "latency_ms":      float,
    "model_version":   str,
  }
"""
from __future__ import annotations

import logging
import time

import numpy as np

logger = logging.getLogger(__name__)

_parselmouth_available: bool | None = None  # None = not yet checked
_librosa_available: bool | None = None
_load_attempted: bool = False
MODEL_VERSION = "prosody-parselmouth-0.4.7"


def load_prosody() -> bool:
    """
    Verify that prosody dependencies are importable.
    Prosody has no heavy model file to load — just library availability.
    """
    global _parselmouth_available, _librosa_available, _load_attempted

    if _load_attempted:
        return _parselmouth_available and _librosa_available

    _load_attempted = True

    try:
        import parselmouth  # noqa: F401
        _parselmouth_available = True
    except ImportError:
        _parselmouth_available = False
        logger.warning("PROSODY_PARSELMOUTH_MISSING",
                       extra={"detail": "Install praat-parselmouth for prosody analysis"})

    try:
        import librosa  # noqa: F401
        _librosa_available = True
    except ImportError:
        _librosa_available = False
        logger.warning("PROSODY_LIBROSA_MISSING",
                       extra={"detail": "Install librosa for speaking rate estimation"})

    available = bool(_parselmouth_available and _librosa_available)
    if available:
        logger.info("PROSODY_READY", extra={"version": MODEL_VERSION})
    return available


def is_loaded() -> bool:
    return bool(_parselmouth_available and _librosa_available)


def get_version() -> str:
    return MODEL_VERSION if is_loaded() else "unavailable"


def run(audio_16k: np.ndarray) -> dict | None:
    """
    Run full prosody analysis on a 16 kHz float32 audio array.

    Minimum input: 0.2 seconds (3,200 samples). For 3-second chunks
    from the gateway this is always satisfied.

    Returns None if parselmouth or librosa are not available.
    """
    if not is_loaded():
        return None

    if len(audio_16k) == 0:
        return None

    from ml.common.constants import SAMPLE_RATE
    from ml.prosody_analysis.anomaly_detector import (
        compute_prosodic_features,
        prosodic_anomaly_score,
    )

    sr = SAMPLE_RATE  # 16000

    t0 = time.perf_counter()
    try:
        # Gather all sub-features (pitch, pauses, rhythm, speaking_rate)
        feats = compute_prosodic_features(audio_16k, sr)

        # Composite anomaly score
        anomaly = prosodic_anomaly_score(feats)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        result = dict(feats)
        result["anomaly_score"] = round(anomaly, 4)
        result["overall_prosody_risk"] = round(anomaly, 4)  # alias for persistence.ts
        result["latency_ms"] = round(latency_ms, 2)
        result["model_version"] = MODEL_VERSION

        # Round all float fields for clean JSON
        for k, v in result.items():
            if isinstance(v, float):
                result[k] = round(v, 4)

        return result

    except Exception as exc:
        logger.error("PROSODY_INFERENCE_ERROR", extra={"error": str(exc)})
        raise
