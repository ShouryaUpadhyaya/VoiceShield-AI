"""Rough speaking-rate estimate via syllable-nuclei peak counting on the envelope."""
from __future__ import annotations
import numpy as np
import librosa
from ml.common.constants import SAMPLE_RATE


def estimate_speaking_rate(y: np.ndarray, sr: int = SAMPLE_RATE) -> float:
    if len(y) < sr * 0.2:
        return 0.0
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    peaks = librosa.util.peak_pick(
        onset_env, pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.3, wait=10
    )
    duration_s = len(y) / sr
    return float(len(peaks) / duration_s) if duration_s > 0 else 0.0
