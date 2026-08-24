"""LFCC + light CNN baseline.

Purpose is comparison, not performance. LFCC-based countermeasures are the
official ASVspoof baseline family, so having one trained under our exact
front-end tells us how much the SSL model is really adding — as opposed to how
much came from the preprocessing and augmentation work.

Linear-frequency cepstral coefficients rather than mel: mel spacing devotes its
resolution to low frequencies where speech content lives, while vocoder
artefacts concentrate in the high band. LFCC keeps that band at full weight.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torchaudio

from ml.common.constants import SAMPLE_RATE


class LFCCFrontEnd(nn.Module):
    def __init__(self, sample_rate: int = SAMPLE_RATE, n_lfcc: int = 60, n_fft: int = 512, hop: int = 160):
        super().__init__()
        self.lfcc = torchaudio.transforms.LFCC(
            sample_rate=sample_rate,
            n_lfcc=n_lfcc,
            speckwargs={"n_fft": n_fft, "hop_length": hop, "win_length": n_fft, "center": False},
        )

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        feats = self.lfcc(waveform)                                # (B, n_lfcc, T)
        delta = torchaudio.functional.compute_deltas(feats)
        ddelta = torchaudio.functional.compute_deltas(delta)
        # Deltas matter more than the statics here: synthesis artefacts show up
        # as unnatural frame-to-frame trajectories.
        return torch.stack([feats, delta, ddelta], dim=1)          # (B, 3, n_lfcc, T)


class LFCCBaseline(nn.Module):
    def __init__(self, n_lfcc: int = 60, channels: int = 32, dropout: float = 0.3):
        super().__init__()
        self.front_end = LFCCFrontEnd(n_lfcc=n_lfcc)

        def block(cin: int, cout: int) -> nn.Sequential:
            return nn.Sequential(
                nn.Conv2d(cin, cout, 3, padding=1),
                nn.BatchNorm2d(cout),
                nn.LeakyReLU(0.1),
                nn.Conv2d(cout, cout, 3, padding=1),
                nn.BatchNorm2d(cout),
                nn.LeakyReLU(0.1),
                nn.MaxPool2d(2),
            )

        self.encoder = nn.Sequential(
            block(3, channels), block(channels, channels * 2), block(channels * 2, channels * 4)
        )
        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1), nn.Flatten(),
            nn.Dropout(dropout), nn.Linear(channels * 4, 1),
        )

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        return self.head(self.encoder(self.front_end(waveform))).squeeze(-1)

    def trainable_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
