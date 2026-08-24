"""Spectral and phase feature front-ends.

The important one here is Modified Group Delay (MGD).

Magnitude-only features — Mel, MFCC, and to a lesser degree LFCC — throw phase
away. Neural vocoders (HiFi-GAN and relatives) reconstruct magnitude
spectrograms convincingly but estimate phase sub-optimally, so phase is exactly
where the artefact that survives a codec lives.

MGD matters for a second reason specific to this project: it measures glottal
phase continuity, which is a property of the human vocal apparatus rather than
of any particular language's phonetics. That makes it a defensible route to
robustness across Indian languages without Indic training data — and it stays
valid if Indic data is added later, because nothing about MGD is language-tuned.

All transforms are torch modules so they run on GPU inside the model's forward
pass, not in the data loader.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torchaudio

from ml.common.constants import SAMPLE_RATE


class ModifiedGroupDelay(nn.Module):
    r"""Modified Group Delay Cepstral features.

    Standard group delay — the negative derivative of the phase spectrum — is
    numerically unusable on speech: it spikes wherever the magnitude spectrum
    approaches a zero, drowning the signal in variance. The modified form
    (Hegde et al.) fixes this by dividing by a cepstrally-smoothed magnitude
    and applying two compression parameters:

        tau(k)     = (X_R·Y_R + X_I·Y_I) / S(k)^(2·gamma)
        tau_mod(k) = sign(tau) · |tau|^alpha

    where X is the DFT of x[n], Y the DFT of n·x[n], and S the smoothed
    magnitude. alpha and gamma in (0, 1] tame the dynamic range; the defaults
    are the values used in the anti-spoofing literature.

    A DCT then decorrelates the result into cepstral coefficients.
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        n_fft: int = 512,
        hop_length: int = 160,
        win_length: int = 400,
        n_cep: int = 30,
        alpha: float = 0.4,
        gamma: float = 0.9,
        smoothing_bins: int = 8,
        eps: float = 1e-8,
    ):
        super().__init__()
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.win_length = win_length
        self.alpha = alpha
        self.gamma = gamma
        self.smoothing_bins = smoothing_bins
        self.eps = eps

        self.register_buffer("window", torch.hann_window(win_length), persistent=False)

        n_freq = n_fft // 2 + 1
        # Orthonormal DCT-II matrix, precomputed once.
        k = torch.arange(n_cep).unsqueeze(1)
        n = torch.arange(n_freq).unsqueeze(0)
        dct = torch.cos(torch.pi * k * (2 * n + 1) / (2 * n_freq))
        dct[0] *= 1 / torch.sqrt(torch.tensor(2.0))
        self.register_buffer("dct", dct * torch.sqrt(torch.tensor(2.0 / n_freq)), persistent=False)

    def _stft(self, waveform: torch.Tensor) -> torch.Tensor:
        return torch.stft(
            waveform,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            win_length=self.win_length,
            window=self.window,
            center=False,
            return_complex=True,
            pad_mode="reflect",
        )

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        """waveform: (B, samples) -> (B, n_cep, frames)"""
        x = self._stft(waveform)

        # Y is the DFT of n*x[n]; the ramp must be applied per analysis frame,
        # not across the whole signal, or the group delay is meaningless.
        frames = waveform.unfold(-1, self.win_length, self.hop_length)  # (B, T, win)
        ramp = torch.arange(self.win_length, device=waveform.device, dtype=waveform.dtype)
        ramped = (frames * ramp * self.window).transpose(1, 2)          # (B, win, T)
        y = torch.fft.rfft(ramped, n=self.n_fft, dim=1)                 # (B, freq, T)

        frames_to_use = min(x.shape[-1], y.shape[-1])
        x, y = x[..., :frames_to_use], y[..., :frames_to_use]

        magnitude = x.abs()

        # Cepstrally-smoothed magnitude S(k): the denominator that makes the
        # group delay stable near spectral zeros.
        log_mag = torch.log(magnitude + self.eps)
        cepstrum = torch.fft.irfft(log_mag, dim=1)
        lifter = torch.zeros(cepstrum.shape[1], device=cepstrum.device, dtype=cepstrum.dtype)
        lifter[: self.smoothing_bins] = 1.0
        lifter[-self.smoothing_bins :] = 1.0
        smoothed = torch.exp(torch.fft.rfft(cepstrum * lifter.view(1, -1, 1), dim=1).real)

        tau = (x.real * y.real + x.imag * y.imag) / (smoothed.abs().pow(2 * self.gamma) + self.eps)
        tau = torch.sign(tau) * tau.abs().pow(self.alpha)

        return torch.matmul(self.dct, tau)


class LFCC(nn.Module):
    """Linear-frequency cepstral coefficients.

    Linear rather than mel spacing on purpose: mel spends its resolution on low
    frequencies where speech content lives, while synthesis artefacts
    concentrate in the high band that mel compresses away.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, n_lfcc: int = 60,
                 n_fft: int = 512, hop_length: int = 160):
        super().__init__()
        self.transform = torchaudio.transforms.LFCC(
            sample_rate=sample_rate,
            n_lfcc=n_lfcc,
            speckwargs={"n_fft": n_fft, "hop_length": hop_length,
                        "win_length": n_fft, "center": False},
        )

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        return self.transform(waveform)


class SpectroTemporalFeatures(nn.Module):
    """LFCC + MGD stacked as channels, each with deltas.

    Magnitude and phase fail in different ways, so a fusion of the two is more
    robust than either — the finding the ASVspoof 5 summary reports for
    multi-feature systems.
    """

    def __init__(self, n_lfcc: int = 60, n_mgd: int = 30, use_mgd: bool = True,
                 use_lfcc: bool = True, deltas: bool = True, cmvn: bool = True):
        super().__init__()
        if not (use_lfcc or use_mgd):
            raise ValueError("at least one of use_lfcc / use_mgd must be enabled")

        self.use_lfcc = use_lfcc
        self.use_mgd = use_mgd
        self.deltas = deltas
        # MGD lands on a much wider numeric range than LFCC (order 100 vs order
        # 10). Concatenating them raw lets MGD dominate the first convolution by
        # scale alone. Per-utterance CMVN puts both on equal footing and, as a
        # bonus, removes the stationary channel component the way cepstral mean
        # subtraction traditionally does.
        self.cmvn = cmvn
        self.lfcc = LFCC(n_lfcc=n_lfcc) if use_lfcc else None
        self.mgd = ModifiedGroupDelay(n_cep=n_mgd) if use_mgd else None

        self.n_coeffs = (n_lfcc if use_lfcc else 0) + (n_mgd if use_mgd else 0)
        self.n_channels = 3 if deltas else 1

    @staticmethod
    def _cmvn(features: torch.Tensor) -> torch.Tensor:
        """Cepstral mean and variance normalisation, per utterance per coefficient."""
        mean = features.mean(dim=-1, keepdim=True)
        std = features.std(dim=-1, keepdim=True).clamp(min=1e-5)
        return (features - mean) / std

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        """waveform: (B, samples) -> (B, channels, coeffs, frames)"""
        parts = []
        if self.lfcc is not None:
            parts.append(self.lfcc(waveform))
        if self.mgd is not None:
            parts.append(self.mgd(waveform))

        # LFCC and MGD can differ by a frame or two at the edges depending on
        # padding; trim to the shorter so they stack cleanly.
        frames = min(p.shape[-1] for p in parts)
        parts = [p[..., :frames] for p in parts]
        if self.cmvn:
            parts = [self._cmvn(p) for p in parts]
        features = torch.cat(parts, dim=1)

        if not self.deltas:
            return features.unsqueeze(1)

        delta = torchaudio.functional.compute_deltas(features)
        ddelta = torchaudio.functional.compute_deltas(delta)
        return torch.stack([features, delta, ddelta], dim=1)
