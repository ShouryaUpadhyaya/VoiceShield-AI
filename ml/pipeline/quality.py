"""Conservative signal integrity gate, not a speech detector or a noise classifier."""
import numpy as np


def assess_audio(audio, sr=16000):
    y = np.asarray(audio)
    reasons, warnings = [], []
    if y.ndim != 1 or y.size == 0 or not np.isfinite(y).all():
        return {"eligible": False, "reasons": ["invalid_audio"], "warnings": []}
    centered = y.astype(np.float64) - float(y.mean())
    rms = float(np.sqrt(np.mean(centered ** 2)))
    dbfs = float(20 * np.log10(max(rms, 1e-12)))
    if len(y) < sr:
        reasons.append("less_than_one_second")
    if dbfs < -60:
        reasons.append("silence_or_dc")
    frame = int(sr * .02)
    frames = [centered[i:i+frame] for i in range(0, len(y), frame)]
    active_seconds = sum(len(f) / sr for f in frames if np.sqrt(np.mean(f*f)) >= .001)
    if active_seconds < .5:
        reasons.append("insufficient_active_audio")
    clip_fraction = float(np.mean(np.abs(y) >= .999))
    if clip_fraction > .01:
        warnings.append("clipping")
    if np.max(np.abs(y)) > 1.01:
        warnings.append("out_of_range_amplitude")
    return {"eligible": not reasons, "reasons": reasons, "warnings": warnings,
            "rms_dbfs": round(dbfs, 2), "active_seconds": round(active_seconds, 3),
            "clipped_fraction": round(clip_fraction, 4), "speech_presence_verified": False}
