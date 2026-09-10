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
        from ml.common.constants import MODEL_PATHS, REPO_ROOT
        from ml.speaker_verification.embeddings.embedding_extractor import EcapaEmbedder

        _savedir = savedir or MODEL_PATHS.get("ecapa_savedir", "models/ecapa")

        _embedder = EcapaEmbedder(savedir=_savedir)
        _model_version = "speechbrain/spkrec-ecapa-voxceleb"
        logger.info("SPEAKER_LOADED", extra={"savedir": _savedir})

        # Try to load enrollment database if present
        enroll_path = REPO_ROOT / "models/enrolled_speakers.npz"
        if enroll_path.exists() and enroll_path.stat().st_size > 100:
            try:
                with np.load(enroll_path, allow_pickle=False) as data:
                    _enrolled_speakers = {k: data[k] for k in data.files
                                          if data[k].shape == (192,) and np.isfinite(data[k]).all()
                                          and np.linalg.norm(data[k]) > 0}
                logger.info("ENROLLMENT_LOADED", extra={"speaker_count": len(_enrolled_speakers)})
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
            "comparison": "gallery_identification",
            "identity_verified": False,
            "decision_threshold": SPEAKER_MATCH_THRESHOLD,
            "calibrated": False,
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
                import re
                result["status"] = "matched"
                result["speaker_id"] = re.sub(r'_part\d+$', '', best_id)
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

def enroll_speaker(speaker_id: str, audio_16k: np.ndarray) -> bool:
    """Enroll a new speaker into the database. Cuts into 15-second chunks to prevent OOM and improve matching."""
    global _enrolled_speakers, _embedder
    if _embedder is None:
        raise ValueError("ECAPA embedder is not loaded.")
    
    if _enrolled_speakers is None:
        _enrolled_speakers = {}
        
    # 15 seconds at 16000 Hz = 240000 samples
    max_samples = 15 * 16000
    num_chunks = max(1, (len(audio_16k) + max_samples - 1) // max_samples)
    
    success = False
    for i in range(num_chunks):
        start = i * max_samples
        end = min((i + 1) * max_samples, len(audio_16k))
        chunk = audio_16k[start:end]
        
        # Skip chunks that are extremely short (less than 1s) unless it's the only one
        if len(chunk) < 16000 and num_chunks > 1:
            continue
            
        embedding = _embedder.embed(chunk, sr=16000)
        chunk_id = speaker_id if num_chunks == 1 else f"{speaker_id}_part{i+1}"
        _enrolled_speakers[chunk_id] = embedding
        success = True
    
    enroll_path = Path("models/enrolled_speakers.npz")
    enroll_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        np.savez(enroll_path, **_enrolled_speakers)
        logger.info(f"Successfully enrolled speaker {speaker_id} (cut into {num_chunks} chunks)")
        return success
    except Exception as e:
        logger.error(f"Failed to save enrollment database: {e}")
        return False

def enroll_directory(directory_path: str) -> dict:
    """Recursively find and enroll all .wav files in a directory."""
    import librosa
    path = Path(directory_path)
    if not path.exists() or not path.is_dir():
        return {"error": f"Directory not found: {directory_path}"}
        
    enrolled = []
    failed = []
    
    for file in path.glob("**/*.wav"):
        try:
            audio, _ = librosa.load(file, sr=16000, mono=True)
            speaker_id = file.stem
            if enroll_speaker(speaker_id, audio):
                enrolled.append(speaker_id)
            else:
                failed.append(speaker_id)
        except Exception as e:
            failed.append(f"{file.stem} ({str(e)})")
            
    return {"enrolled": enrolled, "failed": failed}
