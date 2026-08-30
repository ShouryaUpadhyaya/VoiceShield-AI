"""Torch Dataset over the cached ASVspoof corpus.

Reads the ragged int16 memmap written by ml/data/build_cache.py. Because the
cache holds full-length conditioned audio, every epoch can take a different
random 4 s crop of the same utterance — free augmentation that costs no disk.

Codec variants live in parallel .pcm files with byte-identical offsets (the
augmenter length-matches every round-trip), so switching a sample between its
clean and telephony version is just a different memmap to index into.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from ml.common.audio_utils import FrontEndConfig, pad_or_crop, rms_normalize
from ml.common.constants import PROCESSED_DIR
from ml.deepfake_detection.preprocessing.augment import Augmenter

INT16_SCALE = 32768.0


class CachedSpoofDataset(Dataset):
    def __init__(
        self,
        split: str,
        front_end: FrontEndConfig | None = None,
        augmenter: Augmenter | None = None,
        crop: str = "random",
        variants: tuple[str, ...] = ("clean",),
        cache_dir: Path = PROCESSED_DIR,
        seed: int = 0,
    ):
        self.split = split
        self.cfg = front_end or FrontEndConfig()
        self.augmenter = augmenter
        self.crop = crop
        self.cache_dir = Path(cache_dir)
        self.seed = seed

        index = np.load(self.cache_dir / f"{split}.npz", allow_pickle=True)
        self.offsets = index["offsets"]
        self.keep = index["keep"]
        self.labels = index["labels"].astype(np.int64)
        self.system_ids = index["system_ids"]
        self.speaker_ids = index["speaker_ids"]

        self.variant_paths: list[Path] = []
        for variant in variants:
            name = f"{split}.pcm" if variant == "clean" else f"{split}.{variant}.pcm"
            path = self.cache_dir / name
            if path.exists():
                self.variant_paths.append(path)
        if not self.variant_paths:
            raise FileNotFoundError(f"no cache found for split {split!r} in {self.cache_dir}")

        # memmaps are opened lazily per worker: a memmap handle created in the
        # parent process does not survive fork cleanly under DataLoader workers.
        self._memmaps: list[np.memmap] | None = None

    def __len__(self) -> int:
        return len(self.keep)

    def _mm(self) -> list[np.memmap]:
        if self._memmaps is None:
            self._memmaps = [np.memmap(p, dtype=np.int16, mode="r") for p in self.variant_paths]
        return self._memmaps

    def _rng(self, idx: int) -> np.random.Generator:
        # Seeded per (epoch-agnostic) item + worker so augmentation is random
        # across epochs but reproducible given a seed and worker id.
        info = torch.utils.data.get_worker_info()
        worker = info.id if info else 0
        return np.random.default_rng((self.seed, worker, idx, torch.initial_seed() % (2**31)))

    def raw_audio(self, idx: int, variant: int = 0) -> np.ndarray:
        row = int(self.keep[idx])
        start, end = int(self.offsets[row]), int(self.offsets[row + 1])
        return np.asarray(self._mm()[variant][start:end], dtype=np.int16)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        rng = self._rng(idx)
        variant = int(rng.integers(0, len(self.variant_paths)))
        audio = self.raw_audio(idx, variant).astype(np.float32) / INT16_SCALE

        # Crop before augmenting: augmenting 10 s to then discard 6 s is waste.
        audio = pad_or_crop(audio, self.cfg.segment_samples, mode=self.crop, rng=rng)

        if self.augmenter is not None:
            self.augmenter.rng = rng
            audio = self.augmenter(audio)

        # Normalise LAST so any gain the augmenter applied cannot leak through
        # as a cue, and so train matches the serving path exactly.
        if self.cfg.normalize:
            audio = rms_normalize(audio, self.cfg.target_dbfs)

        return torch.from_numpy(np.ascontiguousarray(audio)), torch.tensor(self.labels[idx])

    # -- helpers for evaluation ------------------------------------------
    def class_counts(self) -> dict[int, int]:
        values, counts = np.unique(self.labels, return_counts=True)
        return {int(v): int(c) for v, c in zip(values, counts)}

    def pos_weight(self) -> float:
        """`pos_weight` for BCEWithLogitsLoss = n_negative / n_positive.

        ASVspoof LA train is ~90% spoof (22800 spoof vs 2580 bonafide), and
        spoof is our positive class, so this comes out below 1.0 — it upweights
        the scarce bonafide examples. Without it the model can score 90%
        accuracy by calling everything fake, which is exactly the failure mode
        that produces false accusations in production."""
        counts = self.class_counts()
        return counts.get(0, 1) / max(counts.get(1, 1), 1)


class VariableLengthCollator:
    """Collate a batch to a single randomly chosen duration.

    The deployment target scores 1.5-2.0 s windows for sub-500 ms alerting,
    while the ASVspoof convention is ~4 s. Training at one fixed length and
    serving at another is precisely the train/serve mismatch this codebase is
    built to avoid, so instead every batch is trained at a length sampled from
    the whole range and the model learns to be duration-agnostic.

    Length is chosen per batch rather than per item because a batch has to be
    one rectangular tensor. Items arrive already randomly cropped to the maximum
    length, so taking the first `L` samples is still a uniformly random window
    of the source utterance — no bias is introduced by slicing from the front.
    """

    def __init__(self, min_samples: int, max_samples: int, seed: int = 0, enabled: bool = True):
        if min_samples > max_samples:
            raise ValueError("min_samples must not exceed max_samples")
        self.min_samples = min_samples
        self.max_samples = max_samples
        self.enabled = enabled
        self._rng = np.random.default_rng(seed)

    def __call__(self, batch):
        audio = torch.stack([item[0] for item in batch])
        labels = torch.stack([item[1] for item in batch])

        if self.enabled and self.min_samples < self.max_samples:
            length = int(self._rng.integers(self.min_samples, self.max_samples + 1))
            # Keep the length a multiple of the SSL encoder's 320-sample stride
            # so the frame count is stable and no partial frame is dropped.
            length = max(self.min_samples, (length // 320) * 320)
            audio = audio[:, :length]

        return audio, labels
