"""
Dhwani adapter — wraps DhwaniDetector with graceful degradation.

DhwaniDetector is already a complete wrapper around the ONNX model.
This adapter adds:
  - Singleton lifecycle management (load once at startup)
  - Graceful handling when the ONNX file is missing
  - Structured output compatible with the pipeline result schema
  - Per-call timing

Dhwani model expectations:
  Input:  float32, 16 kHz, mono, exactly 48,000 samples (3 seconds)
          (internal _prep() handles truncation/padding and mean/var normalization)
  Output: [genuine_logit, synthetic_logit] → softmax probabilities

Semantics of output probabilities:
  probabilities[0] = genuine probability  (higher = more likely real human speech)
  probabilities[1] = synthetic probability (higher = more likely TTS / deepfake)
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Module-level singleton: None = not yet attempted, False = failed to load
_detector = None
_load_attempted: bool = False
_model_version: str = "unavailable"


def load_dhwani(model_path: str | Path | None = None) -> bool:
    """
    Load the Dhwani ONNX model. Call once at service startup.

    Returns True on success, False if the model file is missing or fails to load.
    """
    global _detector, _load_attempted, _model_version

    if _load_attempted:
        return _detector is not None

    _load_attempted = True

    try:
        from ml.deepfake_detection.inference.dhwani_detector import DhwaniDetector
        from ml.common.constants import MODEL_PATHS

        path = Path(model_path or MODEL_PATHS["dhwani_onnx"])

        if not path.exists():
            logger.warning(
                "DHWANI_MODEL_MISSING",
                extra={"path": str(path), "detail": "Dhwani UNAVAILABLE — file not found. "
                        "Download from ayush2635/Dhwani-Multilingual-Deepfake-Audio-Detection-Model."},
            )
            return False

        # Validate it's not a Git LFS pointer (135 bytes or smaller)
        if path.stat().st_size < 1024:
            logger.warning(
                "DHWANI_MODEL_LFS_POINTER",
                extra={
                    "path": str(path),
                    "size_bytes": path.stat().st_size,
                    "detail": "Dhwani ONNX appears to be a Git LFS pointer. Run: git lfs pull",
                },
            )
            return False

        _detector = DhwaniDetector(model_path=str(path))
        _model_version = path.name
        logger.info("DHWANI_LOADED", extra={"path": str(path)})
        return True

    except Exception as exc:
        logger.error("DHWANI_LOAD_ERROR", extra={"error": str(exc)})
        _detector = None
        return False


def is_loaded() -> bool:
    return _detector is not None


def get_version() -> str:
    return _model_version


def run(audio_16k: np.ndarray) -> dict | None:
    """
    Run Dhwani inference on a 16 kHz float32 audio array.

    Parameters
    ----------
    audio_16k : np.ndarray
        Shape (48000,) float32 at 16 kHz. Values in [-1, 1].

    Returns
    -------
    dict | None
        {
          "genuine_probability":   float,   # 0–1; higher = more likely real human
          "synthetic_probability": float,   # 0–1; higher = more likely synthetic/deepfake
          "latency_ms":            float,
          "model_version":         str,
        }
        Returns None if the model is not loaded.
    """
    if _detector is None:
        return None

    t0 = time.perf_counter()
    try:
        result = _detector.predict_with_details(audio_16k)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "genuine_probability":   round(result["genuine_probability"], 4),
            "synthetic_probability": round(result["synthetic_probability"], 4),
            "latency_ms":            round(latency_ms, 2),
            "model_version":         _model_version,
        }
    except Exception as exc:
        logger.error("DHWANI_INFERENCE_ERROR", extra={"error": str(exc)})
        raise
