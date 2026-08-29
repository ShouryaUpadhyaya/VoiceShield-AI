"""Enroll a reference voice (e.g. CEO/CXO) by averaging embeddings across a few clean clips."""
from __future__ import annotations
import numpy as np

from ml.speaker_verification.embeddings.embedding_extractor import get_ecapa_embedder
from ml.common.audio_utils import load_audio


def enroll_speaker(audio_paths: list[str]) -> np.ndarray:
    embedder = get_ecapa_embedder()
    embeddings = []
    for path in audio_paths:
        audio = load_audio(path)
        embeddings.append(embedder.embed(audio))
    return np.mean(np.stack(embeddings, axis=0), axis=0)
