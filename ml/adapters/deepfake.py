"""
Custom deepfake predictor adapter.

The existing DeepfakePredictor (predictor.py) expects either:
  - file path (str | Path)
  - bytes of a supported audio container (WAV, etc.)

For the real-time pipeline we have raw float32 numpy arrays.
We encode float32→WAV bytes in-memory, then pass to predictor.predict().

Predictor's sliding-window approach:
  - 32 windows max, 50% overlap
  - 90th percentile pooling (catches short spoofed segments)
  - Returns: deepfake_probability, is_deepfake, windows_scored, etc.

Model checkpoint search: ARTIFACT_DIR / */best.pt  (sorted by mtime)
Returns None if no checkpoint is found — graceful degradation.
"""
from __future__ import annotations

import io
import logging
import time

import numpy as np

logger = logging.getLogger(__name__)

_predictor = None
_load_attempted: bool = False
_model_version: str = "unavailable"


def load_deepfake(checkpoint_path=None) -> bool:
    """Load custom deepfake predictor. Returns True on success."""
    global _predictor, _load_attempted, _model_version

    if _load_attempted:
        return _predictor is not None

    _load_attempted = True

    try:
        from ml.deepfake_detection.inference.predictor import load_predictor
        pred = load_predictor(checkpoint_path)
        if pred is None:
            logger.warning(
                "DEEPFAKE_NO_CHECKPOINT",
                extra={"detail": "Custom deepfake model UNAVAILABLE — no best.pt checkpoint. "
                        "Train a model or place checkpoint in artifacts/*/best.pt"},
            )
            return False
        _predictor = pred
        _model_version = pred.checkpoint_path.name
        logger.info("DEEPFAKE_LOADED", extra={"checkpoint": str(pred.checkpoint_path)})
        return True
    except ImportError as exc:
        logger.warning("DEEPFAKE_IMPORT_ERROR", extra={"error": str(exc)})
        return False
    except Exception as exc:
        logger.error("DEEPFAKE_LOAD_ERROR", extra={"error": str(exc)})
        return False


def is_loaded() -> bool:
    return _predictor is not None


def get_version() -> str:
    return _model_version


def _float32_to_wav_bytes(audio: np.ndarray, sr: int = 16000) -> bytes:
    """Encode float32 numpy array as in-memory WAV bytes (soundfile)."""
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf.read()


def run(audio_16k: np.ndarray) -> dict | None:
    """
    Run custom deepfake inference on a 16 kHz float32 audio array.

    Returns
    -------
    dict | None
        {
          "deepfake_probability": float,   # 0–1; higher = more likely synthetic
          "is_deepfake":          bool,
          "decision_threshold":   float,
          "windows_scored":       int,
          "pooling":              "p90",
          "latency_ms":           float,
          "model_version":        str,
        }
        Returns None if model is not loaded.
    """
    if _predictor is None:
        return None

    t0 = time.perf_counter()
    try:
        wav_bytes = _float32_to_wav_bytes(audio_16k)
        result = _predictor.predict(wav_bytes)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "deepfake_probability": result["deepfake_probability"],
            "is_deepfake":          result["is_deepfake"],
            "decision_threshold":   result["decision_threshold"],
            "windows_scored":       result["windows_scored"],
            "pooling":              "p90",
            "latency_ms":           round(latency_ms, 2),
            "model_version":        _model_version,
        }
    except Exception as exc:
        logger.error("DEEPFAKE_INFERENCE_ERROR", extra={"error": str(exc)})
        raise
