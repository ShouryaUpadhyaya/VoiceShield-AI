"""Jitter/shimmer/HNR — voice-quality microstructure often disturbed by synthesis."""
from __future__ import annotations
import numpy as np
import parselmouth
from parselmouth.praat import call
from ml.common.constants import SAMPLE_RATE


def extract_voice_quality(y: np.ndarray, sr: int = SAMPLE_RATE) -> dict:
    snd = parselmouth.Sound(y, sampling_frequency=sr)
    try:
        point_process = call(snd, "To PointProcess (periodic, cc)", 75, 500)
        jitter = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
        shimmer = call([snd, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
        harmonicity = snd.to_harmonicity_cc()
        hnr = call(harmonicity, "Get mean", 0, 0)
    except Exception:
        jitter, shimmer, hnr = 0.0, 0.0, 0.0

    def clean(v):
        return float(v) if v == v else 0.0  # filter NaN

    return {"jitter": clean(jitter), "shimmer": clean(shimmer), "hnr": clean(hnr)}
