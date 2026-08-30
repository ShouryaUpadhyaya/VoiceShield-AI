"""Combines all prosodic sub-features into a normalized anomaly score."""
from __future__ import annotations
import numpy as np

from ml.common.constants import SAMPLE_RATE
from ml.prosody_analysis.pitch import extract_pitch_stats
from ml.prosody_analysis.pauses import extract_pause_stats
from ml.prosody_analysis.rhythm import extract_voice_quality
from ml.prosody_analysis.speaking_rate import estimate_speaking_rate

# Natural human speech reference bounds: (optimal_min, optimal_max, weight)
REFERENCE_BOUNDS = {
    "f0_std": (15.0, 50.0, 1.0),            # Pitch dynamism
    "jitter": (0.001, 0.012, 1.2),          # Micro-pitch stability
    "shimmer": (0.010, 0.060, 1.2),         # Micro-amplitude stability
    "hnr": (12.0, 28.0, 0.8),               # Harmonics-to-noise ratio
    "mean_pause_ratio": (0.10, 0.45, 0.8),   # Natural respiration / pause ratio
}


def _continuous_penalty(value: float, opt_min: float, opt_max: float) -> float:
    """Computes smooth monotonic penalty when metric deviates from optimal range."""
    if opt_min <= value <= opt_max:
        return 0.0
    if value < opt_min:
        diff = opt_min - value
        scale = max(opt_min * 0.5, 1e-4)
    else:
        diff = value - opt_max
        scale = max((opt_max - opt_min) * 0.5, 1e-4)
    return float(1.0 - np.exp(-0.5 * (diff / scale) ** 2))


def compute_prosodic_features(y: np.ndarray, sr: int = SAMPLE_RATE) -> dict:
    feats = {}
    feats.update(extract_pitch_stats(y, sr))
    feats.update(extract_pause_stats(y, sr))
    feats.update(extract_voice_quality(y, sr))
    feats["speaking_rate"] = estimate_speaking_rate(y, sr)
    return feats


def prosodic_anomaly_score(feats: dict) -> float:
    penalties = []
    weights = []
    for key, (opt_min, opt_max, w) in REFERENCE_BOUNDS.items():
        if key in feats:
            p = _continuous_penalty(float(feats[key]), opt_min, opt_max)
            penalties.append(p * w)
            weights.append(w)
    if not penalties:
        return 0.0
    return float(np.clip(np.sum(penalties) / (np.sum(weights) + 1e-6), 0.0, 1.0))
