"""Tests for training-time augmentation."""

from __future__ import annotations

import numpy as np
import pytest

from ml.common.constants import SAMPLE_RATE, SEGMENT_SAMPLES
from ml.deepfake_detection.preprocessing.augment import (
    Augmenter,
    AugmentConfig,
    apply_codec,
    available_codecs,
    match_length,
    rawboost,
)


@pytest.fixture
def audio() -> np.ndarray:
    t = np.arange(SEGMENT_SAMPLES) / SAMPLE_RATE
    return (0.3 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)


def test_rawboost_preserves_shape_and_changes_signal(audio):
    out = rawboost(audio, np.random.default_rng(0))
    assert out.shape == audio.shape and out.dtype == np.float32
    assert np.isfinite(out).all()
    assert not np.allclose(out, audio)


@pytest.mark.parametrize("algo", [1, 2, 3, 4])
def test_rawboost_algorithms(audio, algo):
    out = rawboost(audio, np.random.default_rng(algo), algo)
    assert out.shape == audio.shape and np.isfinite(out).all()


def test_codec_roundtrip_keeps_length_and_band_limits(audio):
    """A telephony codec must (a) not change the tensor shape and (b) actually
    remove high-frequency content — if it doesn't, the augmentation is a no-op
    and the robustness claim is empty."""
    codecs = available_codecs()
    if "amr_nb" not in codecs:
        pytest.skip("amr_nb encoder unavailable in this ffmpeg build")

    out = apply_codec(audio, "amr_nb")
    assert out.shape == audio.shape

    def high_band_energy(x):
        spectrum = np.abs(np.fft.rfft(x))
        freqs = np.fft.rfftfreq(x.size, 1 / SAMPLE_RATE)
        return float(spectrum[freqs > 4000].sum() / (spectrum.sum() + 1e-9))

    assert high_band_energy(out) < high_band_energy(audio) + 1e-6


def test_match_length_both_directions():
    assert match_length(np.zeros(100, np.float32), 60).size == 60
    assert match_length(np.ones(60, np.float32), 100).size == 100


def test_augmenter_output_contract(audio):
    aug = Augmenter(AugmentConfig(rawboost_prob=1.0, gain_prob=1.0), seed=0)
    for _ in range(10):
        out = aug(audio)
        assert out.shape == audio.shape
        assert out.dtype == np.float32
        assert np.isfinite(out).all()
        assert np.abs(out).max() <= 1.0, "augmentation must never leave samples past full scale"


def test_augmenter_varies_between_calls(audio):
    aug = Augmenter(AugmentConfig(rawboost_prob=1.0), seed=0)
    outs = [aug(audio) for _ in range(5)]
    assert len({o.tobytes() for o in outs}) == 5


def test_codec_prob_defaults_off():
    """Online codec augmentation costs ~650 ms/utt and would starve the GPU;
    it is precomputed offline instead. This test pins that decision."""
    assert AugmentConfig().codec_prob == 0.0
