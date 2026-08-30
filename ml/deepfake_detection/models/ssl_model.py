"""Frozen self-supervised front-end + trainable spoof head.

Why frozen: fine-tuning WavLM-large end-to-end (the 1.26% EER recipe) needs
~24 GB of VRAM. This machine has 4 GB. Freezing the SSL encoder and training
only a light back-end fits in ~1.5 GB, trains in minutes per epoch, and still
captures most of the benefit — the SSL representation is doing the heavy
lifting either way.

Two ideas do the work here:

1. Learned layer weighting. Spoofing artefacts do not live in the last
   transformer layer; lower layers carry more of the phase/spectral detail that
   betrays a vocoder. So we take a softmax-weighted sum over ALL hidden states
   and let training decide which depths matter, rather than guessing.

2. Attentive statistics pooling. A clip is spoofed because of what happens in
   specific frames (a bad transient, an over-smooth formant), not on average.
   ASP lets the model weight frames before pooling, and keeps the weighted
   standard deviation as well as the mean.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoConfig, AutoModel


class AttentiveStatsPooling(nn.Module):
    def __init__(self, dim: int, bottleneck: int = 128):
        super().__init__()
        self.attention = nn.Sequential(
            nn.Conv1d(dim, bottleneck, kernel_size=1),
            nn.ReLU(),
            nn.BatchNorm1d(bottleneck),
            nn.Tanh(),
            nn.Conv1d(bottleneck, dim, kernel_size=1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, D) -> (B, 2D)
        x = x.transpose(1, 2)
        weights = torch.softmax(self.attention(x), dim=-1)
        mean = torch.sum(x * weights, dim=-1)
        var = torch.sum(weights * x.pow(2), dim=-1) - mean.pow(2)
        std = torch.sqrt(var.clamp(min=1e-7))
        return torch.cat([mean, std], dim=1)


class SSLSpoofDetector(nn.Module):
    def __init__(
        self,
        ssl_name: str = "microsoft/wavlm-base-plus",
        freeze_ssl: bool = True,
        hidden_dim: int = 256,
        dropout: float = 0.3,
        use_layer_weights: bool = True,
    ):
        super().__init__()
        self.ssl_name = ssl_name
        self.freeze_ssl = freeze_ssl

        self.ssl = AutoModel.from_pretrained(ssl_name, output_hidden_states=True)
        config = AutoConfig.from_pretrained(ssl_name)
        feat_dim = config.hidden_size
        n_layers = config.num_hidden_layers + 1  # + the CNN feature projection

        if freeze_ssl:
            self.ssl.eval()
            for param in self.ssl.parameters():
                param.requires_grad = False

        self.use_layer_weights = use_layer_weights
        self.layer_weights = nn.Parameter(torch.zeros(n_layers)) if use_layer_weights else None

        self.pool = AttentiveStatsPooling(feat_dim)
        self.classifier = nn.Sequential(
            nn.BatchNorm1d(feat_dim * 2),
            nn.Linear(feat_dim * 2, hidden_dim),
            nn.LeakyReLU(0.1),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.LeakyReLU(0.1),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

    def train(self, mode: bool = True):
        """Keep the frozen encoder in eval mode permanently.

        Without this, .train() would re-enable dropout inside WavLM and make the
        'frozen' features non-deterministic between epochs — a subtle source of
        noise that looks like the head failing to converge.
        """
        super().train(mode)
        if self.freeze_ssl:
            self.ssl.eval()
        return self

    def extract(self, waveform: torch.Tensor) -> torch.Tensor:
        context = torch.no_grad() if self.freeze_ssl else torch.enable_grad()
        with context:
            outputs = self.ssl(waveform)

        if self.use_layer_weights:
            stacked = torch.stack(outputs.hidden_states, dim=0)  # (L, B, T, D)
            weights = torch.softmax(self.layer_weights, dim=0).view(-1, 1, 1, 1)
            return (stacked * weights).sum(dim=0)
        return outputs.last_hidden_state

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        """waveform: (B, samples) float32 in [-1, 1]. Returns logits (B,)."""
        features = self.extract(waveform)
        return self.classifier(self.pool(features)).squeeze(-1)

    def trainable_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def layer_importance(self) -> list[float]:
        """Inspectable: which SSL depths the head actually relies on."""
        if not self.use_layer_weights:
            return []
        return torch.softmax(self.layer_weights.detach().cpu(), dim=0).tolist()
