"""ECAPA-TDNN speaker-embedding extraction via SpeechBrain's pretrained model."""
from __future__ import annotations
import numpy as np
import torch
from pathlib import Path
from speechbrain.inference.speaker import EncoderClassifier
from speechbrain.utils.fetching import LocalStrategy

from ml.common.constants import SAMPLE_RATE, MODEL_PATHS


class EcapaEmbedder:
    def __init__(self, savedir: str = "models/ecapa"):
        local = Path(savedir).resolve()
        required = ["hyperparams.yaml", "embedding_model.ckpt", "mean_var_norm_emb.ckpt", "classifier.ckpt", "label_encoder.txt"]
        source = str(local) if all((local / name).is_file() for name in required) else MODEL_PATHS["ecapa_source"]
        self.model = EncoderClassifier.from_hparams(
            source=source,
            savedir=savedir,
            overrides={"pretrained_path": str(local)} if source == str(local) else {},
            run_opts={"device": "cpu"},
            local_strategy=LocalStrategy.COPY,
        )

    def embed(self, audio: np.ndarray, sr: int = SAMPLE_RATE) -> np.ndarray:
        """Returns a 192-d speaker embedding for one utterance."""
        if sr != SAMPLE_RATE or audio.ndim != 1 or not np.isfinite(audio).all():
            raise ValueError("ECAPA requires finite mono 16 kHz audio")
        wav_tensor = torch.from_numpy(audio).float().unsqueeze(0)  # (1, T)
        with torch.no_grad():
            emb = self.model.encode_batch(wav_tensor)  # (1, 1, 192)
        return emb.squeeze().cpu().numpy()


_embedder_singleton: EcapaEmbedder | None = None


def get_ecapa_embedder() -> EcapaEmbedder:
    global _embedder_singleton
    if _embedder_singleton is None:
        _embedder_singleton = EcapaEmbedder()
    return _embedder_singleton
