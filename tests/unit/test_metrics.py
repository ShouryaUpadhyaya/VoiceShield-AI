"""Tests for detection metrics, checked against analytically known answers."""

from __future__ import annotations

import numpy as np
import pytest

from ml.deepfake_detection.evaluation.metrics import (
    compute_det_curve,
    compute_eer,
    metrics_at_threshold,
    per_attack_eer,
)


def test_perfect_separation_gives_zero_eer():
    rng = np.random.default_rng(0)
    scores = np.concatenate([rng.normal(-5, 0.5, 500), rng.normal(5, 0.5, 500)])
    labels = np.array([0] * 500 + [1] * 500)
    assert compute_eer(scores, labels)[0] == pytest.approx(0.0, abs=1e-9)


def test_random_scores_give_chance_eer():
    rng = np.random.default_rng(1)
    eer, _ = compute_eer(rng.normal(size=8000), rng.integers(0, 2, 8000))
    assert eer == pytest.approx(0.5, abs=0.03)


def test_eer_matches_analytic_value():
    """Two unit-variance Gaussians separated by 2*z(0.9) overlap at exactly 10%."""
    rng = np.random.default_rng(2)
    n = 40000
    scores = np.concatenate([rng.normal(0, 1, n), rng.normal(2 * 1.2815515655, 1, n)])
    labels = np.array([0] * n + [1] * n)
    assert compute_eer(scores, labels)[0] == pytest.approx(0.10, abs=0.01)


def test_higher_score_means_spoof():
    """Sign convention is load-bearing: inverting it turns the detector inside
    out while still producing a plausible-looking EER."""
    scores = np.array([0.1, 0.2, 0.8, 0.9])
    labels = np.array([0, 0, 1, 1])
    assert compute_eer(scores, labels)[0] == pytest.approx(0.0)
    assert compute_eer(-scores, labels)[0] == pytest.approx(1.0)


def test_det_curve_endpoints():
    rng = np.random.default_rng(3)
    far, frr, _ = compute_det_curve(rng.normal(size=200), rng.integers(0, 2, 200))
    assert far[0] == pytest.approx(1.0) and frr[0] == pytest.approx(0.0)
    assert far[-1] == pytest.approx(0.0) and frr[-1] == pytest.approx(1.0)


def test_single_class_rejected():
    with pytest.raises(ValueError):
        compute_eer(np.array([0.1, 0.2]), np.array([1, 1]))


def test_operating_point_units():
    scores = np.array([0.9, 0.8, 0.2, 0.1])
    labels = np.array([1, 0, 1, 0])
    m = metrics_at_threshold(scores, labels, 0.5)
    assert m["confusion"] == {"tp": 1, "tn": 1, "fp": 1, "fn": 1}
    assert m["false_alarm_rate"] == pytest.approx(0.5)  # genuine callers flagged
    assert m["miss_rate"] == pytest.approx(0.5)         # deepfakes let through


def test_per_attack_eer_isolates_a_weak_attack():
    """One attack the model cannot see must not be hidden by the average."""
    rng = np.random.default_rng(4)
    bona = rng.normal(0, 1, 2000)
    easy = rng.normal(6, 1, 1000)   # trivially detected
    hard = rng.normal(0, 1, 1000)   # indistinguishable from genuine

    scores = np.concatenate([bona, easy, hard])
    labels = np.array([0] * 2000 + [1] * 2000)
    systems = np.array(["-"] * 2000 + ["A01"] * 1000 + ["A02"] * 1000)

    result = per_attack_eer(scores, labels, systems)
    assert result["A01"] < 0.02
    assert result["A02"] > 0.4
