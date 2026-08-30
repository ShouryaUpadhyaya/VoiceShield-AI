"""
Speaker verification adapter — ECAPA-TDNN via SpeechBrain.

IMPORTANT: An embedding alone is NOT speaker verification.
Without an enrollment database, we cannot assert "this is speaker X".

We return:
  {
    "status": "embedding_only",
    "embedding_dimension": 192,
  }

When an enrollment database exists (models/enrolled_speakers.npz), we attempt
cosine similarity comparison against enrolled embeddings and return:
  {
    "status": "matched" | "unmatched" | "no_enrollment",
    "speaker_id": str | null,
    "similarity": float | null,
    "embedding_dimension": 192,
  }

EcapaEmbedder input:
  audio: float32 numpy array, 16 kHz (any length)
  sr:    int = 16000

EcapaEmbedder output:
  np.ndarray of shape (192,) — L2-normalized embedding
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

_embedder = None
_load_attempted: bool = False
_model_version: str = "unavailable"
_enrolled_speakers: dict | None = None  # {speaker_id: embedding_array}

# Cosine similarity threshold for speaker match
SPEAKER_MATCH_THRESHOLD = 0.75


def load_speaker(savedir: str | None = None) -> bool:
    """Load ECAPA-TDNN model. Returns True on success."""
    global _embedder, _load_attempted, _model_version, _enrolled_speakers

    if _load_attempted:
        return _embedder is not None

    _load_attempted = True

    try:
        from ml.common.constants import MODEL_PATHS
        from ml.speaker_verification.embeddings.embedding_extractor import EcapaEmbedder

        _savedir = savedir or MODEL_PATHS.get("ecapa_savedir", "models/ecapa")

        _embedder = EcapaEmbedder(savedir=_savedir)
        _model_version = "speechbrain/spkrec-ecapa-voxceleb"
        logger.info("SPEAKER_LOADED", extra={"savedir": _savedir})

        # Try to load enrollment database if present
        enroll_path = Path("models/enrolled_speakers.npz")
        if enroll_path.exists() and enroll_path.stat().st_size > 100:
            try:
                data = np.load(enroll_path, allow_pickle=False)
                _enrolled_speakers = {k: data[k] for k in data.files}
                logger.info("ENROLLMENT_LOADED", extra={"speakers": list(_enrolled_speakers.keys())})
            except Exception as e:
                logger.warning("ENROLLMENT_LOAD_FAILED", extra={"error": str(e)})

        return True

    except ImportError as exc:
        logger.warning(
            "SPEAKER_IMPORT_ERROR",
            extra={"error": str(exc), "detail": "speechbrain not installed — speaker UNAVAILABLE"},
        )
        return False
    except Exception as exc:
        logger.error(
            "SPEAKER_LOAD_ERROR",
            extra={"error": str(exc), "detail": "ECAPA model files may be missing (Git LFS not pulled)"},
        )
        return False


def is_loaded() -> bool:
    return _embedder is not None


def get_version() -> str:
    return _model_version


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two L2-normalized vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def run(audio_16k: np.ndarray) -> dict | None:
    """
    Generate ECAPA speaker embedding and optionally compare against enrollment.

    Returns
    -------
    dict | None
        {
          "status":               "embedding_only" | "matched" | "unmatched" | "no_enrollment",
          "speaker_id":           str | null,
          "similarity":           float | null,
          "embedding_dimension":  192,
          "latency_ms":           float,
          "model_version":        str,
        }
        Returns None if model is not loaded.
    """
    if _embedder is None:
        return None

    t0 = time.perf_counter()
    try:
        embedding = _embedder.embed(audio_16k, sr=16000)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        # Base result — embedding only
        result: dict = {
            "status": "embedding_only",
            "speaker_id": None,
            "similarity": None,
            "embedding_dimension": int(embedding.shape[0]),
            "latency_ms": round(latency_ms, 2),
            "model_version": _model_version,
        }

        # Attempt enrollment comparison if database is loaded
        if _enrolled_speakers:
            best_id = None
            best_sim = -1.0

            for speaker_id, enrolled_emb in _enrolled_speakers.items():
                sim = _cosine_similarity(embedding, enrolled_emb)
                if sim > best_sim:
                    best_sim = sim
                    best_id = speaker_id

            if best_sim >= SPEAKER_MATCH_THRESHOLD:
                result["status"] = "matched"
                result["speaker_id"] = best_id
                result["similarity"] = round(best_sim, 4)
            else:
                result["status"] = "unmatched"
                result["similarity"] = round(best_sim, 4)
        else:
            result["status"] = "no_enrollment"

        # NOTE: Do NOT log or return raw embedding values — privacy
        return result

    except Exception as exc:
        logger.error("SPEAKER_INFERENCE_ERROR", extra={"error": str(exc)})
        raise
