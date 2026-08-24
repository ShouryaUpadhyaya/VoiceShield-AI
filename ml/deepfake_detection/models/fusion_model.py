"""SSL + spectral fusion detector.

This is the architecture the blueprint recommends for production: a
self-supervised foundation model providing generalisation, fused with a
lightweight spectral network that reads high-frequency and phase artefacts
the SSL branch is not specialised for.

The two branches fail in different ways, which is the point:

* The **SSL branch** (frozen WavLM, learned layer weighting, attentive stats
  pooling) generalises across unseen synthesis methods, but is known to lean on
  speaker identity as a shortcut and degrades under codec mismatch.
* The **spectral branch** reads LFCC (high-frequency magnitude) and MGD (glottal
  phase continuity) — both computed from the signal itself, with no learned
  notion of who is speaking. MGD in particular is language-agnostic, which is
  what keeps this defensible across Indian languages without Indic training
  data.

Fusion is by concatenating pooled embeddings before the classifier rather than
averaging two independent scores, so the head can learn *when* to trust each
branch instead of weighting them equally at every operating point.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from ml.deepfake_detection.models.ssl_model import AttentiveStatsPooling, SSLSpoofDetector
from ml.deepfake_detection.preprocessing.feature_extraction import SpectroTemporalFeatures


class SEBlock(nn.Module):
    """Squeeze-and-excitation: lets the branch reweight coefficient bands.

    Useful here because which band carries the artefact depends on the codec —
    under AMR-NB everything above 4 kHz is gone and the network needs to shift
    its attention downward.
    """

    def __init__(self, channels: int, reduction: int = 8):
        super().__init__()
        self.gate = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(channels, max(channels // reduction, 4)),
            nn.ReLU(),
            nn.Linear(max(channels // reduction, 4), channels),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * self.gate(x).unsqueeze(-1).unsqueeze(-1)


class SpectralBranch(nn.Module):
    """Small residual CNN over stacked LFCC + MGD cepstra."""

    def __init__(self, n_lfcc: int = 60, n_mgd: int = 30, channels: int = 32,
                 embed_dim: int = 128, use_mgd: bool = True, use_lfcc: bool = True):
        super().__init__()
        self.features = SpectroTemporalFeatures(
            n_lfcc=n_lfcc, n_mgd=n_mgd, use_mgd=use_mgd, use_lfcc=use_lfcc
        )

        def block(cin: int, cout: int, pool: tuple[int, int]) -> nn.Sequential:
            return nn.Sequential(
                nn.Conv2d(cin, cout, 3, padding=1),
                nn.BatchNorm2d(cout),
                nn.LeakyReLU(0.1),
                nn.Conv2d(cout, cout, 3, padding=1),
                nn.BatchNorm2d(cout),
                nn.LeakyReLU(0.1),
                SEBlock(cout),
                nn.MaxPool2d(pool),
            )

        # Pool hard on the coefficient axis, gently on time: time resolution is
        # what carries the transient artefacts.
        self.encoder = nn.Sequential(
            block(self.features.n_channels, channels, (2, 2)),
            block(channels, channels * 2, (2, 2)),
            block(channels * 2, channels * 4, (2, 1)),
        )
        self.project = nn.Linear(channels * 4, embed_dim)
        self.pool = AttentiveStatsPooling(embed_dim)
        self.embed_dim = embed_dim * 2

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        x = self.encoder(self.features(waveform))     # (B, C, F, T)
        x = x.mean(dim=2).transpose(1, 2)             # (B, T, C) — collapse coeff axis
        return self.pool(self.project(x))             # (B, 2*embed_dim)


class FusionSpoofDetector(nn.Module):
    def __init__(
        self,
        ssl_name: str = "microsoft/wavlm-base-plus",
        freeze_ssl: bool = True,
        hidden_dim: int = 256,
        dropout: float = 0.3,
        use_layer_weights: bool = True,
        spectral_channels: int = 32,
        spectral_embed: int = 128,
        use_mgd: bool = True,
        use_lfcc: bool = True,
    ):
        super().__init__()
        self.ssl_branch = SSLSpoofDetector(
            ssl_name=ssl_name, freeze_ssl=freeze_ssl,
            hidden_dim=hidden_dim, dropout=dropout,
            use_layer_weights=use_layer_weights,
        )
        self.spectral_branch = SpectralBranch(
            channels=spectral_channels, embed_dim=spectral_embed,
            use_mgd=use_mgd, use_lfcc=use_lfcc,
        )

        ssl_dim = self.ssl_branch.pool.attention[0].in_channels * 2
        fused_dim = ssl_dim + self.spectral_branch.embed_dim

        self.classifier = nn.Sequential(
            nn.BatchNorm1d(fused_dim),
            nn.Linear(fused_dim, hidden_dim),
            nn.LeakyReLU(0.1),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.LeakyReLU(0.1),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

    def train(self, mode: bool = True):
        super().train(mode)
        self.ssl_branch.train(mode)  # keeps the frozen encoder in eval mode
        return self

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        ssl_embed = self.ssl_branch.pool(self.ssl_branch.extract(waveform))
        spectral_embed = self.spectral_branch(waveform)
        return self.classifier(torch.cat([ssl_embed, spectral_embed], dim=1)).squeeze(-1)

    def trainable_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def layer_importance(self) -> list[float]:
        return self.ssl_branch.layer_importance()
