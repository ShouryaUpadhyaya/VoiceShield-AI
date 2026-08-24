"""Deepfake detection service.

Backed by the Dhwani Multilingual ONNX model.
Loaded once at application startup to preserve latency budget.
"""

from __future__ import annotations

import logging

from app.services.deepfake.dhwani_detector import DeepfakeUnavailable, load_detector, get_detector

__all__ = ["analyze_deepfake", "warm_up", "get_predictor", "DeepfakeUnavailable"]

logger = logging.getLogger(__name__)

def warm_up(checkpoint_path: str | None = None) -> bool:
    """Called at startup. Returns whether a model is ready."""
    try:
        detector = load_detector()
    except DeepfakeUnavailable as e:
        logger.warning(f"no deepfake checkpoint found — /analyze/audio will report model_unavailable: {e}")
        return False
    except Exception:
        logger.exception("failed to load deepfake checkpoint")
        return False

    if detector is None:
        return False

    return True

def get_predictor():
    """Alias for health checks in main.py."""
    detector = get_detector()
    if detector:
        # Dummy structure matching old health check expectations
        class DummyPredictor:
            def __init__(self, d):
                self.checkpoint_path = type("obj", (object,), {"name": getattr(d, "model_path", "dhwani_onnx")})
                self.dev_eer = 0.0
                self.device = getattr(d, "execution_provider", "unknown")
        return DummyPredictor(detector)
    return None

def analyze_deepfake(filename: str, audio_bytes: bytes) -> dict:
    """Score one audio upload.

    Returns the full evidence dict, not a bare float: the risk engine needs the
    probability, the UI shows the per-window breakdown, and both need to know
    when the answer is unavailable.
    """
    detector = get_detector()
    if detector is None:
        raise DeepfakeUnavailable("no deepfake model loaded")

    try:
        prediction = detector.predict(audio_bytes)
    except ValueError as exc:
        raise ValueError(f"could not decode {filename!r}: {exc}") from exc

    return prediction.model_dump()
