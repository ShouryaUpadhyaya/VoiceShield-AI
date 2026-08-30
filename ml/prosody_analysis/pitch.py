"""Pitch (F0) extraction and variability via Parselmouth (Praat bindings)."""
from __future__ import annotations
import numpy as np
import parselmouth
from ml.common.constants import SAMPLE_RATE


def extract_pitch_stats(y: np.ndarray, sr: int = SAMPLE_RATE) -> dict:
    snd = parselmouth.Sound(y, sampling_frequency=sr)
    pitch = snd.to_pitch()
    f0 = pitch.selected_array["frequency"]
    f0_voiced = f0[f0 > 0]

    if len(f0_voiced) < 2:
        return {"f0_mean": 0.0, "f0_std": 0.0, "f0_range": 0.0, "voiced_ratio": 0.0}

    return {
        "f0_mean": float(np.mean(f0_voiced)),
        "f0_std": float(np.std(f0_voiced)),
        "f0_range": float(np.max(f0_voiced) - np.min(f0_voiced)),
        "voiced_ratio": float(len(f0_voiced) / max(len(f0), 1)),
    }
