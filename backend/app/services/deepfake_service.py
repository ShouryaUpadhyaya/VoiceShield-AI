"""Deepfake detection service.

Backed by the trained countermeasure in ml/deepfake_detection. The model is
loaded once at application startup (see app.main lifespan) because loading a
95M-parameter encoder per request would dominate the latency budget.

If no checkpoint is present the service reports that explicitly rather than
inventing a number — an unavailable detector must never look like a confident
"genuine" verdict to the risk engine downstream.
"""

from __future__ import annotations

import logging

from ml.common.audio_utils import AudioDecodeError
from ml.deepfake_detection.inference.predictor import get_predictor, load_predictor

__all__ = ["analyze_deepfake", "warm_up", "get_predictor", "DeepfakeUnavailable"]

logger = logging.getLogger(__name__)


class DeepfakeUnavailable(RuntimeError):
    """No usable model. The caller must degrade, not guess."""


def warm_up(checkpoint_path: str | None = None) -> bool:
    """Called at startup. Returns whether a model is ready."""
    try:
        predictor = load_predictor(checkpoint_path)
    except Exception:
        logger.exception("failed to load deepfake checkpoint")
        return False

    if predictor is None:
        logger.warning("no deepfake checkpoint found — /analyze/audio will report model_unavailable")
        return False

    logger.info(
        "deepfake model ready: %s (dev EER %.2f%%)",
        predictor.checkpoint_path.name,
        (predictor.dev_eer or 0) * 100,
    )
    return True


def analyze_deepfake(filename: str, audio_bytes: bytes) -> dict:
    """Score one audio upload.

    Returns the full evidence dict, not a bare float: the risk engine needs the
    probability, the UI shows the per-window breakdown, and both need to know
    when the answer is unavailable.
    """
    predictor = get_predictor()
    if predictor is None:
        raise DeepfakeUnavailable("no deepfake model loaded")

    try:
        result = predictor.predict(audio_bytes)
    except AudioDecodeError as exc:
        raise ValueError(f"could not decode {filename!r}: {exc}") from exc

    result["available"] = True
    return result
