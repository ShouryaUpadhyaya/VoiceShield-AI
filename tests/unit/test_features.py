"""Tests for the spectral/phase front-ends and variable-length collation."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from ml.common.constants import SAMPLE_RATE
from ml.deepfake_detection.preprocessing.dataset import VariableLengthCollator
from ml.deepfake_detection.preprocessing.feature_extraction import (
    LFCC,
    ModifiedGroupDelay,
    SpectroTemporalFeatures,
)


@pytest.fixture
def voiced() -> torch.Tensor:
    """Harmonic stack with vibrato — closer to speech than white noise."""
    t = torch.arange(64600) / SAMPLE_RATE
    f0 = 140 * (1 + 0.03 * torch.sin(2 * torch.pi * 5 * t))
    phase = 2 * torch.pi * torch.cumsum(f0, 0) / SAMPLE_RATE
    sig = sum((1.0 / h) * torch.sin(h * phase) for h in range(1, 25))
    return (sig / sig.abs().max() * 0.5).unsqueeze(0)


def phase_randomised(signal: torch.Tensor) -> torch.Tensor:
    """Same magnitude spectrum, destroyed phase structure."""
    spectrum = torch.fft.rfft(signal, dim=-1)
    randomised = spectrum.abs() * torch.exp(1j * torch.rand_like(spectrum.real) * 2 * torch.pi)
    out = torch.fft.irfft(randomised, n=signal.shape[-1], dim=-1)
    return out / out.abs().max() * 0.5


def test_mgd_output_is_finite_and_shaped(voiced):
    out = ModifiedGroupDelay(n_cep=30)(voiced)
    assert out.shape[0] == 1 and out.shape[1] == 30
    assert torch.isfinite(out).all(), "MGD must not produce NaN/inf — the raw group delay does"


def test_mgd_is_more_phase_sensitive_than_lfcc(voiced):
    """The reason MGD is in the model at all.

    Against a twin with an identical magnitude spectrum but randomised phase,
    a phase-based feature must react more than a magnitude-only one. If this
    ever fails, MGD has stopped earning its compute.
    """
    torch.manual_seed(0)
    twin = phase_randomised(voiced)

    def relative_change(module):
        a, b = module(voiced), module(twin)
        n = min(a.shape[-1], b.shape[-1])
        return float((a[..., :n] - b[..., :n]).abs().mean() / (a[..., :n].abs().mean() + 1e-9))

    assert relative_change(ModifiedGroupDelay()) > relative_change(LFCC())


def test_cmvn_puts_branches_on_the_same_scale(voiced):
    """Raw MGD runs an order of magnitude larger than LFCC; without CMVN it
    would dominate the first convolution by scale alone."""
    features = SpectroTemporalFeatures(cmvn=True)(voiced)
    assert abs(float(features.mean())) < 0.1
    assert float(features.abs().max()) < 50


@pytest.mark.parametrize("n_samples", [32000, 40000, 48000, 64600])
def test_features_handle_variable_length(n_samples):
    out = SpectroTemporalFeatures()(torch.randn(2, n_samples).clamp(-1, 1))
    assert out.shape[:3] == (2, 3, 90)
    assert out.shape[3] > 0


def test_feature_config_requires_at_least_one_branch():
    with pytest.raises(ValueError):
        SpectroTemporalFeatures(use_lfcc=False, use_mgd=False)


def test_mgd_can_be_disabled_for_ablation():
    """Indic scope may grow later; the branch must be switchable so an
    LFCC-only ablation is one config flag, not a code change."""
    out = SpectroTemporalFeatures(use_mgd=False)(torch.randn(2, 64600))
    assert out.shape[2] == 60


def test_collator_yields_one_length_per_batch():
    collator = VariableLengthCollator(32000, 64600, seed=0)
    batch = [(torch.randn(64600), torch.tensor(1)) for _ in range(4)]
    audio, labels = collator(batch)
    assert audio.shape[0] == 4 and labels.shape[0] == 4
    assert 32000 <= audio.shape[1] <= 64600


def test_collator_length_is_stride_aligned():
    """A length that is not a multiple of the SSL encoder's 320-sample stride
    drops a partial frame and makes the frame count jitter."""
    collator = VariableLengthCollator(32000, 64600, seed=1)
    for _ in range(20):
        audio, _ = collator([(torch.randn(64600), torch.tensor(0)) for _ in range(2)])
        assert audio.shape[1] % 320 == 0


def test_collator_actually_varies():
    collator = VariableLengthCollator(32000, 64600, seed=2)
    lengths = {collator([(torch.randn(64600), torch.tensor(0))] * 2)[0].shape[1] for _ in range(15)}
    assert len(lengths) > 1


def test_collator_disabled_keeps_full_length():
    collator = VariableLengthCollator(32000, 64600, seed=0, enabled=False)
    audio, _ = collator([(torch.randn(64600), torch.tensor(0)) for _ in range(3)])
    assert audio.shape[1] == 64600


def test_collator_rejects_inverted_range():
    with pytest.raises(ValueError):
        VariableLengthCollator(64600, 32000)
