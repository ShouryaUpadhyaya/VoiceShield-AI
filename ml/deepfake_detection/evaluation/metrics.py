"""Detection metrics for spoof countermeasures.

EER and min t-DCF are the two numbers the ASVspoof literature reports, so they
are the two numbers that let us say where we stand against published work.
Accuracy is deliberately not the headline metric: the LA corpus is ~90% spoof,
so a model that answers "fake" every time scores 90% accuracy and is useless.
"""

from __future__ import annotations

import numpy as np


def compute_det_curve(scores: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """False-alarm and miss rates across every threshold.

    Convention: higher score = more likely SPOOF. label 1 = spoof.
      - miss  = a spoof that slipped through (scored low)
      - false alarm = a genuine caller wrongly flagged
    """
    scores = np.asarray(scores, dtype=np.float64).ravel()
    labels = np.asarray(labels).ravel()

    n_spoof = int((labels == 1).sum())
    n_bona = int((labels == 0).sum())
    if n_spoof == 0 or n_bona == 0:
        raise ValueError("need both classes present to compute a DET curve")

    order = np.argsort(scores, kind="mergesort")
    sorted_labels = labels[order]
    thresholds = np.concatenate([[-np.inf], scores[order]])

    # At threshold t, everything with score <= t is called bonafide.
    spoof_below = np.concatenate([[0], np.cumsum(sorted_labels == 1)])
    bona_below = np.concatenate([[0], np.cumsum(sorted_labels == 0)])

    miss_rates = spoof_below / n_spoof
    false_alarm_rates = (n_bona - bona_below) / n_bona
    return false_alarm_rates, miss_rates, thresholds


def compute_eer(scores: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    """Equal error rate and the threshold that achieves it."""
    far, frr, thresholds = compute_det_curve(scores, labels)
    idx = int(np.nanargmin(np.abs(far - frr)))
    return float((far[idx] + frr[idx]) / 2.0), float(thresholds[idx])


def compute_min_tdcf(
    cm_scores: np.ndarray,
    cm_labels: np.ndarray,
    p_target: float = 0.05,
    p_spoof: float = 0.05,
    c_miss: float = 1.0,
    c_fa: float = 10.0,
    c_fa_spoof: float = 10.0,
    asv_miss_rate: float = 0.0,
    asv_fa_rate: float = 0.0,
) -> float:
    """Normalised minimum tandem DCF (ASVspoof 2019 formulation).

    The full t-DCF is defined against a specific ASV system's error rates. We
    have no ASV system in the loop yet, so the defaults reduce it to a
    cost-weighted DET minimum. Treat this as CM-only t-DCF and label it that
    way in any report — quoting it as the challenge t-DCF without the official
    ASV scores would be an unfair comparison.
    """
    far, frr, _ = compute_det_curve(cm_scores, cm_labels)

    c1 = c_miss * p_target * (1 - asv_miss_rate)
    c2 = c_fa * (1 - p_target - p_spoof) * asv_fa_rate + c_fa_spoof * p_spoof

    costs = c1 * frr + c2 * far
    norm = min(c1, c2)
    return float(np.min(costs) / norm) if norm > 0 else float("nan")


def metrics_at_threshold(scores: np.ndarray, labels: np.ndarray, threshold: float) -> dict:
    """Operating-point metrics for the threshold we actually ship.

    The API returns a decision, not a curve, so these are the numbers that
    describe what a user experiences.
    """
    scores = np.asarray(scores).ravel()
    labels = np.asarray(labels).ravel()
    predicted = (scores >= threshold).astype(int)

    tp = int(((predicted == 1) & (labels == 1)).sum())
    tn = int(((predicted == 0) & (labels == 0)).sum())
    fp = int(((predicted == 1) & (labels == 0)).sum())
    fn = int(((predicted == 0) & (labels == 1)).sum())

    return {
        "threshold": float(threshold),
        "accuracy": (tp + tn) / max(len(labels), 1),
        "precision": tp / max(tp + fp, 1),
        "recall_spoof": tp / max(tp + fn, 1),
        "false_alarm_rate": fp / max(fp + tn, 1),  # genuine callers wrongly flagged
        "miss_rate": fn / max(fn + tp, 1),         # deepfakes let through
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
    }


def per_attack_eer(scores: np.ndarray, labels: np.ndarray, system_ids: np.ndarray) -> dict[str, float]:
    """EER per attack algorithm, each measured against the full bonafide pool.

    A single headline EER hides that a detector can be near-perfect on six
    attacks and blind to a seventh — which is precisely what happens when a new
    TTS system appears in the wild.
    """
    scores = np.asarray(scores).ravel()
    labels = np.asarray(labels).ravel()
    system_ids = np.asarray(system_ids).ravel()

    bona = labels == 0
    out: dict[str, float] = {}
    for attack in sorted(set(system_ids[labels == 1])):
        mask = bona | ((labels == 1) & (system_ids == attack))
        eer, _ = compute_eer(scores[mask], labels[mask])
        out[str(attack)] = eer
    return out
