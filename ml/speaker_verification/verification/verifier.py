"""Cosine-similarity speaker verification against an enrolled reference embedding."""
from __future__ import annotations
import numpy as np


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a_n = a / (np.linalg.norm(a) + 1e-9)
    b_n = b / (np.linalg.norm(b) + 1e-9)
    return float(np.dot(a_n, b_n))


def speaker_mismatch_score(
    live_embedding: np.ndarray,
    enrolled_embedding: np.ndarray,
    match_threshold: float = 0.65,
) -> float:
    """Returns mismatch risk in [0,1]:
    - 0.0 = confident match (same speaker identity)
    - 1.0 = confident mismatch (impostor / different speaker)
    """
    sim = cosine_similarity(live_embedding, enrolled_embedding)
    if sim >= 0.95:
        return 0.0
    if sim >= match_threshold:
        return float(np.clip((0.95 - sim) / (0.95 - match_threshold) * 0.30, 0.0, 1.0))
    return float(np.clip(0.30 + (match_threshold - sim) / (match_threshold + 0.1) * 0.70, 0.30, 1.0))
