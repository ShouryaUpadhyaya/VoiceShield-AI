"""Serving-side predictor.

Loaded once at FastAPI startup and reused. Three things matter here and each
one is a bug we would otherwise ship:

1. The front-end comes from the checkpoint, not from defaults. If a model was
   trained with silence_policy="keep", serving it with "trim_edges" quietly
   shifts the input distribution and the scores stop meaning anything.

2. Long audio is scored as overlapping windows, not one arbitrary 4 s crop. A
   90 s call contains a few seconds of synthetic speech; scoring one centre
   crop can miss it entirely. We pool with a high quantile rather than the mean
   so a short spoofed segment is not averaged away by surrounding genuine audio.

3. The probability is temperature-calibrated. The UI prints this number to a
   human who will act on it.
"""

from __future__ import annotations

import threading
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch

from ml.common.audio_utils import (
    AudioDecodeError,
    FrontEndConfig,
    preprocess,
    rms_normalize,
    sliding_windows,
)
from ml.common.constants import ARTIFACT_DIR
from ml.deepfake_detection.models.classifier import build_model

# Cap the windows scored for one request so a 10-minute upload cannot pin the
# GPU. 32 windows at 50% overlap covers ~66 s of audio.
MAX_WINDOWS = 32


class DeepfakePredictor:
    def __init__(self, checkpoint_path: str | Path, device: str | None = None):
        self.checkpoint_path = Path(checkpoint_path)
        if not self.checkpoint_path.exists():
            raise FileNotFoundError(f"no checkpoint at {self.checkpoint_path}")

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        checkpoint = torch.load(self.checkpoint_path, map_location=self.device, weights_only=False)

        self.front_end = FrontEndConfig(**checkpoint["front_end"])
        self.threshold = float(checkpoint.get("dev_threshold", 0.0))
        self.temperature = float(checkpoint.get("temperature", 1.0))
        self.dev_eer = checkpoint.get("dev_eer_full", checkpoint.get("dev_eer"))

        self.model = build_model(checkpoint["model_name"], **checkpoint["model_kwargs"])
        self.model.load_state_dict(checkpoint["model_state"])
        self.model.to(self.device).eval()

        # A single GPU with 4 GB cannot serve concurrent requests safely; the
        # lock serialises them instead of letting two requests OOM each other.
        self._lock = threading.Lock()

    @torch.no_grad()
    def _score_windows(self, windows: np.ndarray) -> np.ndarray:
        batch = torch.from_numpy(windows).to(self.device)
        with self._lock:
            logits = self.model(batch)
        return logits.float().cpu().numpy()

    def predict(self, source: str | Path | bytes) -> dict:
        """Returns the calibrated spoof probability plus the evidence behind it."""
        audio = preprocess(source, self.front_end, fixed_length=False)

        windows = sliding_windows(audio, self.front_end.segment_samples)
        if len(windows) > MAX_WINDOWS:
            picks = np.linspace(0, len(windows) - 1, MAX_WINDOWS).astype(int)
            windows = windows[picks]

        if self.front_end.normalize:
            windows = np.stack([rms_normalize(w, self.front_end.target_dbfs) for w in windows])

        logits = self._score_windows(np.ascontiguousarray(windows, dtype=np.float32))
        calibrated = logits / self.temperature
        probs = 1.0 / (1.0 + np.exp(-calibrated))

        # Max-ish pooling: a call is compromised if ANY stretch of it is
        # synthetic. The 90th percentile keeps that sensitivity without letting
        # one noisy window decide the verdict outright.
        pooled = float(np.quantile(probs, 0.9)) if len(probs) > 1 else float(probs[0])
        threshold_prob = float(1.0 / (1.0 + np.exp(-self.threshold / self.temperature)))

        return {
            "deepfake_probability": round(pooled, 4),
            "is_deepfake": bool(pooled >= threshold_prob),
            "decision_threshold": round(threshold_prob, 4),
            "windows_scored": int(len(probs)),
            "window_probabilities": [round(float(p), 4) for p in probs],
            "audio_seconds": round(audio.size / self.front_end.sample_rate, 2),
            "model": {
                "checkpoint": self.checkpoint_path.name,
                "dev_eer": round(float(self.dev_eer), 4) if self.dev_eer is not None else None,
                "front_end": asdict(self.front_end),
            },
        }


_PREDICTOR: DeepfakePredictor | None = None


def load_predictor(checkpoint_path: str | Path | None = None) -> DeepfakePredictor | None:
    """Process-wide singleton. Returns None if no checkpoint is available yet,
    so the API can fall back rather than refuse to start."""
    global _PREDICTOR
    if _PREDICTOR is not None:
        return _PREDICTOR

    if checkpoint_path is None:
        candidates = sorted(ARTIFACT_DIR.glob("*/best.pt"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            return None
        checkpoint_path = candidates[0]

    _PREDICTOR = DeepfakePredictor(checkpoint_path)
    return _PREDICTOR


def get_predictor() -> DeepfakePredictor | None:
    return _PREDICTOR


__all__ = ["DeepfakePredictor", "load_predictor", "get_predictor", "AudioDecodeError"]
