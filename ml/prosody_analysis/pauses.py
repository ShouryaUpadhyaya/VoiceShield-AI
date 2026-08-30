"""Pause-pattern extraction: silence segment count/duration from voiced intervals."""
from __future__ import annotations
import numpy as np
import parselmouth
from ml.common.constants import SAMPLE_RATE


def extract_pause_stats(y: np.ndarray, sr: int = SAMPLE_RATE, silence_db: float = -25.0) -> dict:
    snd = parselmouth.Sound(y, sampling_frequency=sr)
    intensity = snd.to_intensity()
    values = intensity.values.flatten()
    if len(values) == 0:
        return {"pause_count": 0, "mean_pause_ratio": 0.0}

    threshold = np.max(values) + silence_db
    is_silent = values < threshold
    # count contiguous silent runs
    diffs = np.diff(is_silent.astype(int))
    pause_count = int(np.sum(diffs == 1))
    silent_ratio = float(np.mean(is_silent))

    return {"pause_count": pause_count, "mean_pause_ratio": silent_ratio}
