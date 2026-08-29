"""Spectral and phase feature front-ends, plus DSP anomaly extraction.

This file contains both the PyTorch modules for the Deepfake model (MGD, SpectroTemporalFeatures)
and the numpy/librosa features for the rule-based Prosody Anomaly pipeline.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torchaudio
import numpy as np
import librosa
from scipy.fftpack import dct

from ml.common.constants import SAMPLE_RATE

# --- Deepfake Model Features (PyTorch) --------------------------------------

class ModifiedGroupDelay(nn.Module):
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
        x = self._stft(waveform)
        frames = waveform.unfold(-1, self.win_length, self.hop_length)
        ramp = torch.arange(self.win_length, device=waveform.device, dtype=waveform.dtype)
        ramped = (frames * ramp * self.window).transpose(1, 2)
        y = torch.fft.rfft(ramped, n=self.n_fft, dim=1)

        frames_to_use = min(x.shape[-1], y.shape[-1])
        x, y = x[..., :frames_to_use], y[..., :frames_to_use]

        magnitude = x.abs()
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
    def __init__(self, n_lfcc: int = 60, n_mgd: int = 30, use_mgd: bool = True,
                 use_lfcc: bool = True, deltas: bool = True, cmvn: bool = True):
        super().__init__()
        if not (use_lfcc or use_mgd):
            raise ValueError("at least one of use_lfcc / use_mgd must be enabled")

        self.use_lfcc = use_lfcc
        self.use_mgd = use_mgd
        self.deltas = deltas
        self.cmvn = cmvn
        self.lfcc = LFCC(n_lfcc=n_lfcc) if use_lfcc else None
        self.mgd = ModifiedGroupDelay(n_cep=n_mgd) if use_mgd else None

        self.n_coeffs = (n_lfcc if use_lfcc else 0) + (n_mgd if use_mgd else 0)
        self.n_channels = 3 if deltas else 1

    @staticmethod
    def _cmvn(features: torch.Tensor) -> torch.Tensor:
        mean = features.mean(dim=-1, keepdim=True)
        std = features.std(dim=-1, keepdim=True).clamp(min=1e-5)
        return (features - mean) / std

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        parts = []
        if self.lfcc is not None:
            parts.append(self.lfcc(waveform))
        if self.mgd is not None:
            parts.append(self.mgd(waveform))

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


# --- DSP Anomaly Features (Numpy) -------------------------------------------

N_MFCC = 20
N_FFT = 512
HOP_LENGTH_NP = 160  # 10ms @ 16kHz
N_MELS = 40

def extract_mfcc(y: np.ndarray, sr: int = SAMPLE_RATE) -> np.ndarray:
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC, n_fft=N_FFT, hop_length=HOP_LENGTH_NP)
    delta = librosa.feature.delta(mfcc)
    delta2 = librosa.feature.delta(mfcc, order=2)
    stacked = np.concatenate([mfcc, delta, delta2], axis=0)
    return np.concatenate([stacked.mean(axis=1), stacked.std(axis=1)])

def extract_lfcc(y: np.ndarray, sr: int = SAMPLE_RATE, n_lfcc: int = 20) -> np.ndarray:
    stft = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH_NP)) ** 2
    linear_fb = np.linspace(0, sr / 2, stft.shape[0])
    fb_matrix = np.eye(stft.shape[0])
    linear_spec = fb_matrix @ stft
    log_spec = np.log(linear_spec + 1e-10)
    lfcc = dct(log_spec, type=2, axis=0, norm="ortho")[:n_lfcc]
    return np.concatenate([lfcc.mean(axis=1), lfcc.std(axis=1)])

def extract_cqcc(y: np.ndarray, sr: int = SAMPLE_RATE, n_bins: int = 60, n_coeff: int = 20) -> np.ndarray:
    cqt = np.abs(librosa.cqt(y, sr=sr, n_bins=n_bins, bins_per_octave=12))
    log_cqt = np.log(cqt + 1e-10)
    cqcc = dct(log_cqt, type=2, axis=0, norm="ortho")[:n_coeff]
    return np.concatenate([cqcc.mean(axis=1), cqcc.std(axis=1)])

def extract_spectral(y: np.ndarray, sr: int = SAMPLE_RATE) -> np.ndarray:
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=N_FFT, hop_length=HOP_LENGTH_NP)
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, n_fft=N_FFT, hop_length=HOP_LENGTH_NP)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, n_fft=N_FFT, hop_length=HOP_LENGTH_NP)
    flatness = librosa.feature.spectral_flatness(y=y, n_fft=N_FFT, hop_length=HOP_LENGTH_NP)
    flux = np.diff(np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH_NP)), axis=1)
    flux_energy = np.sqrt(np.sum(flux ** 2, axis=0) + 1e-12)

    feats = [centroid, bandwidth, rolloff, flatness]
    out = [f.mean() for f in feats] + [f.std() for f in feats]
    out += [flux_energy.mean(), flux_energy.std()]
    return np.array(out, dtype=np.float32)

def extract_all_features(y: np.ndarray, sr: int = SAMPLE_RATE) -> np.ndarray:
    mfcc = extract_mfcc(y, sr)
    lfcc_feat = extract_lfcc(y, sr)
    cqcc = extract_cqcc(y, sr)
    spectral = extract_spectral(y, sr)
    return np.concatenate([mfcc, lfcc_feat, cqcc, spectral]).astype(np.float32)

def rule_based_dsp_anomaly_score(feat_vec: np.ndarray, feat_mean: np.ndarray, feat_std: np.ndarray) -> float:
    z = np.abs((feat_vec - feat_mean) / (feat_std + 1e-6))
    score = np.tanh(z.mean() / 3.0)
    return float(np.clip(score, 0.0, 1.0))
