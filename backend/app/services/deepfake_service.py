"""Deepfake detection service — model-agnostic, with an explicit fallback chain.

Resolution order, first one that loads wins:

  1. FUSION   — our trained WavLM + LFCC/MGD model (dev EER 0.55%).
                Needs torch and a checkpoint under ml/artifacts/. Validated.
  2. DHWANI   — ONNX, CPU-only, no torch. Indic-capable. NOT validated
                (~30% EER on ASVspoof, which is out-of-domain for it).
  3. DEMO     — deterministic filename heuristic so the UI can be shown when
                no model is present. Always flagged demo_mode=true.

Every response states which backend produced it and whether that backend has
been validated, so a score can never be mistaken for something it isn't.

Select explicitly with VOICESHIELD_DETECTOR = fusion | dhwani | demo.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
DHWANI_PATH = Path(os.getenv("DHWANI_MODEL_PATH", ROOT / "data/external_models/dhwani/best_model.onnx"))

_detector = None
_backend = "none"


class DeepfakeUnavailable(RuntimeError):
    """No usable model AND demo mode disabled. The caller must degrade, not guess."""


def _try_fusion():
    try:
        import torch  # noqa: F401
    except ImportError:
        logger.info("torch not installed — skipping fusion backend")
        return None
    try:
        from ml.deepfake_detection.inference.predictor import load_predictor
        p = load_predictor()
        if p is None:
            logger.info("no fusion checkpoint found under ml/artifacts/")
        return p
    except Exception:
        logger.exception("fusion backend failed to load")
        return None


def _try_dhwani():
    try:
        from ml.deepfake_detection.inference.dhwani_detector import DhwaniDetector
        if not DHWANI_PATH.exists():
            logger.info("Dhwani model not present at %s", DHWANI_PATH)
            return None
        return DhwaniDetector(DHWANI_PATH)
    except Exception:
        logger.exception("Dhwani backend failed to load")
        return None


def warm_up(force: str | None = None) -> bool:
    """Load a detector once, at startup. Returns whether a real model is ready."""
    global _detector, _backend
    choice = (force or os.getenv("VOICESHIELD_DETECTOR", "auto")).lower()

    order = {"fusion": [("fusion", _try_fusion)],
             "dhwani": [("dhwani", _try_dhwani)],
             "demo":   [],
             "auto":   [("fusion", _try_fusion), ("dhwani", _try_dhwani)]}.get(choice, [])

    for name, loader in order:
        d = loader()
        if d is not None:
            _detector, _backend = d, name
            logger.info("deepfake backend ready: %s", name)
            return True

    _detector, _backend = None, "demo"
    logger.warning("no detector loaded — running in DEMO MODE (scores are not measurements)")
    return False


def get_predictor():
    return _detector


def backend_name() -> str:
    return _backend


def _demo_score(filename: str) -> dict:
    """Deterministic stand-in so the UI is demonstrable with no model present.

    Deliberately NOT random: a demo that changes its answer between runs of the
    same file is worse than one that is obviously a stub.
    """
    name = (filename or "").lower()
    prob = 0.88 if ("fake" in name or "spoof" in name or "clone" in name) else 0.12
    return {
        "deepfake_probability": prob,
        "available": False,
        "demo_mode": True,
        "validated": False,
        "model": "demo-filename-heuristic",
        "windows_scored": 0,
        "warning": "NO MODEL LOADED — this number is a placeholder, not a measurement.",
    }


def analyze_deepfake_window(pcm) -> dict:
    """Score an in-memory float32 window.

    The streaming path already holds decoded PCM. Re-encoding it to a container
    just so the decoder can parse it back is a pointless round-trip that also
    cannot work — headerless PCM has no format for libsndfile or ffmpeg to
    detect. The shared front-end accepts an ndarray directly, so we use that.
    """
    if _detector is None:
        return _demo_score("stream")
    return _score(pcm, "stream")


def analyze_deepfake(filename: str, audio_bytes: bytes) -> dict:
    """Score one encoded audio payload (an upload). Says which backend answered."""
    if _detector is None:
        return _demo_score(filename)
    return _score(audio_bytes, filename)


def _score(source, filename: str) -> dict:

    from ml.common.audio_utils import AudioDecodeError
    try:
        if _backend == "dhwani":
            r = _detector.predict(source)
            return {
                "deepfake_probability": r.deepfake_probability,
                "windows_scored": r.windows_scored,
                "window_probabilities": r.window_probabilities,
                "audio_seconds": r.audio_seconds,
                "model": r.model,
                "validated": r.validated,
                "available": True,
                "demo_mode": False,
                "warning": None if r.validated else
                           "UNVALIDATED MODEL — Dhwani has not been evaluated on in-domain data.",
            }
        out = _detector.predict(source)
        out.update({"available": True, "demo_mode": False, "validated": True,
                    "model": out.get("model", {}).get("checkpoint", "fusion")
                             if isinstance(out.get("model"), dict) else "fusion",
                    "warning": None})
        return out
    except AudioDecodeError as exc:
        raise ValueError(f"could not decode {filename!r}: {exc}") from exc
