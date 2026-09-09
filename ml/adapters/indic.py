"""
Indic adapter — wraps the VoiceShield Indic deepfake detector.

This adapter adds:
  - Singleton lifecycle management (load once at startup)
  - Structured output compatible with the pipeline result schema
  - Graceful handling when the model is missing
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
import os

import numpy as np

logger = logging.getLogger(__name__)

_detector = None
_load_attempted: bool = False
_model_version: str = "unavailable"


def load_indic() -> bool:
    """Load the Indic detector. Returns True on success."""
    global _detector, _load_attempted, _model_version

    if _load_attempted:
        return _detector is not None

    _load_attempted = True

    try:
        from ml.deepfake_detection.indic.detectors.voiceshield_backend import VoiceShieldDetector

        # Checkpoint resolution, most-preferred first. iv15 supersedes v0.1: on 45 real
        # Indic call recordings v0.1 false-accused 71.1% of genuine speech (median
        # p_spoof 0.9946) where iv15 flagged 2.2% (median 0.0000). The failure is not
        # preprocessing -- trim on/off moves v0.1 only 71.1% -> 75.6%, and scoring the
        # original .ogg gives 68.2% -- it is the checkpoint. v0.1 is kept only as a
        # last-resort fallback and says so loudly when it is used.
        #
        # The threshold, spoof_index and trim contract are read FROM the checkpoint by
        # VoiceShieldDetector, so switching files carries the matching operating point
        # (iv15 0.332, v0.1 0.806) with no constant to update here.
        here = Path(__file__).parent.parent
        frozen = here / "deepfake_detection" / "indic" / "frozen"
        env = os.getenv("VOICESHIELD_INDIC_CHECKPOINT")
        candidates = [Path(env)] if env else [
            frozen / "voiceshield-indic-iv15.pth",
            frozen / "best_model.pth",
        ]
        ckpt_path = next((c for c in candidates if c.exists() and c.stat().st_size >= 1024), None)

        if ckpt_path is None:
            logger.warning(
                "INDIC_MODEL_MISSING",
                extra={"searched": [str(c) for c in candidates],
                       "detail": "Indic model UNAVAILABLE — no checkpoint found. Set "
                                 "VOICESHIELD_INDIC_CHECKPOINT or place iv15 at "
                                 f"{frozen / 'voiceshield-indic-iv15.pth'}."},
            )
            return False

        if ckpt_path.name == "voiceshield-indic-v0.1.pth":
            logger.warning(
                "INDIC_SUPERSEDED_CHECKPOINT",
                extra={"path": str(ckpt_path),
                       "detail": "Falling back to v0.1, which false-accuses ~71% of "
                                 "genuine Indic call audio. Provision iv15 instead."},
            )

        # Validate it's not a Git LFS pointer (candidates already filter on size; this
        # keeps the explicit diagnostic for an explicitly-configured path)
        if ckpt_path.stat().st_size < 1024:
            logger.warning(
                "INDIC_MODEL_LFS_POINTER",
                extra={
                    "path": str(ckpt_path),
                    "size_bytes": ckpt_path.stat().st_size,
                    "detail": "Indic checkpoint appears to be a Git LFS pointer. Run: git lfs pull",
                },
            )
            return False

        _detector = VoiceShieldDetector(checkpoint=ckpt_path)
        _model_version = _detector.version
        logger.info("INDIC_LOADED", extra={"path": str(ckpt_path), "version": _model_version})
        return True
    except Exception as exc:
        logger.error("INDIC_LOAD_ERROR", extra={"error": str(exc)}, exc_info=True)
        return False


def is_loaded() -> bool:
    return _detector is not None


def get_version() -> str:
    return _model_version


def run(audio_16k: np.ndarray) -> dict | None:
    """
    Run Indic deepfake inference on a 16 kHz float32 audio array.

    Returns
    -------
    dict | None
        {
          "synthetic_probability": float,   # 0–1; higher = more likely synthetic
          "genuine_probability":   float,   # 0–1; higher = more likely real human
          "latency_ms":            float,
          "model_version":         str,
        }
        Returns None if model is not loaded.
    """
    if _detector is None:
        return None

    t0 = time.perf_counter()
    try:
        result = _detector.predict(audio_16k)
        
        latency_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "synthetic_probability": result.fake_probability,
            "genuine_probability":   result.real_probability,
            "latency_ms":            round(latency_ms, 2),
            "model_version":         _model_version,
            "decision_threshold":    result.threshold,
            "verdict":               result.verdict,
            "windows_scored":        result.windows_scored,
        }
    except Exception as exc:
        logger.error("INDIC_INFERENCE_ERROR", extra={"error": str(exc)})
        raise
