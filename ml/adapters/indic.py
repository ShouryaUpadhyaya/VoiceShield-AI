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
        
        # Path to the frozen weights inside our copied directory
        here = Path(__file__).parent.parent
        ckpt_path = here / "deepfake_detection" / "indic" / "frozen" / "voiceshield-indic-v0.1.pth"
        
        if not ckpt_path.exists():
            logger.warning(
                "INDIC_MODEL_MISSING",
                extra={"path": str(ckpt_path), "detail": "Indic model UNAVAILABLE — file not found."},
            )
            return False

        # Validate it's not a Git LFS pointer
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
        }
    except Exception as exc:
        logger.error("INDIC_INFERENCE_ERROR", extra={"error": str(exc)})
        raise
