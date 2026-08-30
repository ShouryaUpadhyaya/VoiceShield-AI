"""ECAPA-TDNN speaker-embedding extraction via SpeechBrain's pretrained model."""
from __future__ import annotations
import numpy as np
import torch
from speechbrain.inference.speaker import EncoderClassifier
from speechbrain.utils.fetching import LocalStrategy

from ml.common.constants import SAMPLE_RATE, MODEL_PATHS


class EcapaEmbedder:
    def __init__(self, savedir: str = "models/ecapa"):
        self.model = EncoderClassifier.from_hparams(
            source=MODEL_PATHS["ecapa_source"],
            savedir=savedir,
            run_opts={"device": "cpu"},
            local_strategy=LocalStrategy.COPY,
        )

    def embed(self, audio: np.ndarray, sr: int = SAMPLE_RATE) -> np.ndarray:
        """Returns a 192-d speaker embedding for one utterance."""
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
