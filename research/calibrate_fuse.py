"""Calibration and fusion, fitted on DEV ONLY. No test clip influences any parameter.

Phases 8, 9, 17-21, 23, 24, 27, 30, 51-53.

The split discipline is the whole point of this file:
  * calibrators and fusion weights are fitted on the internal `dev` split;
  * model selection between fusion candidates uses grouped cross-validation INSIDE
    dev, never test;
  * `test`, `test_f5`, `test_iv` and everything in the external set (FLEURS,
    XTTS-v2, FreeVC24) are scored exactly once, at the end, and never inform a choice.

Calibration maps each detector's private score space to a common evidence scale so
that adding them is meaningful. Without it, averaging a RawNet2 posterior, an ONNX
softmax and a hand-bounded prosody penalty is arithmetic on incommensurable units.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
WT = Path("/home/aayushdwivedi/Projects/voiceguard-wt/voiceshield")
EPS = 1e-6


# ----------------------------------------------------------------- metrics ---
def eer(pos, neg):
    """pos = bonafide evidence for genuine clips, neg = for spoof. Higher = genuine."""
    s = np.concatenate([pos, neg])
    y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
    o = np.argsort(-s); ys = y[o]
    frr = 1 - np.cumsum(ys) / ys.sum()
    far = np.cumsum(1 - ys) / (len(ys) - ys.sum())
    i = int(np.nanargmin(np.abs(frr - far)))
    return 100 * (frr[i] + far[i]) / 2, float(s[o][i])


def auc(pos, neg):
    s = np.concatenate([pos, neg])
    y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
    r = np.argsort(np.argsort(s)) + 1
    return float((r[y == 1].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def cllr(llr_pos, llr_neg):
    """Application-independent calibration loss (Brummer). Lower is better; 1.0 = a
    system carrying no information. Unlike EER this PUNISHES bad calibration."""
    a = np.mean(np.log2(1 + np.exp(-llr_pos)))
    b = np.mean(np.log2(1 + np.exp(llr_neg)))
    return float((a + b) / 2)


def min_cllr(llr_pos, llr_neg):
    """C_llr after an optimal monotonic (PAV) recalibration -- the discrimination
    floor. C_llr - min_C_llr is the part that is purely bad calibration."""
    from sklearn.isotonic import IsotonicRegression
    s = np.concatenate([llr_pos, llr_neg])
    y = np.r_[np.ones(len(llr_pos)), np.zeros(len(llr_neg))]
    p = IsotonicRegression(out_of_bounds="clip", y_min=EPS, y_max=1 - EPS).fit_transform(s, y)
    l = np.log(p / (1 - p))
    return cllr(l[y == 1], l[y == 0])


def brier(p_pos, p_neg):
    return float((np.sum((1 - p_pos) ** 2) + np.sum(p_neg ** 2)) / (len(p_pos) + len(p_neg)))


def ece(p, y, bins=10):
    """Expected calibration error against the empirical rate of genuine."""
    edges = np.linspace(0, 1, bins + 1)
    tot = 0.0
    for i in range(bins):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= 1)
        if m.sum():
            tot += m.sum() / len(p) * abs(p[m].mean() - y[m].mean())
    return float(tot)


# ------------------------------------------------------------- calibrators ---
class Identity:
    name = "raw (uncalibrated)"
    def fit(self, s, y): return self
    def llr(self, s): return s


class Platt:
    """Logistic-regression calibration -- the BOSARIS/ASVspoof standard. Maps a raw
    score to a log-likelihood ratio with a scale and a shift, fitted on dev."""
    name = "logistic (Platt)"
    def fit(self, s, y):
        from sklearn.linear_model import LogisticRegression
        self.m = LogisticRegression(C=1e6, max_iter=1000).fit(s.reshape(-1, 1), y)
        return self
    def llr(self, s):
        return (self.m.coef_[0][0] * s + self.m.intercept_[0])


class Isotonic:
    """Non-parametric monotonic calibration. More flexible, more prone to overfit on
    a small dev set, and it cannot extrapolate beyond the dev score range."""
    name = "isotonic"
    def fit(self, s, y):
        from sklearn.isotonic import IsotonicRegression
        self.m = IsotonicRegression(out_of_bounds="clip", y_min=EPS, y_max=1 - EPS).fit(s, y)
        return self
    def llr(self, s):
        p = np.clip(self.m.predict(s), EPS, 1 - EPS)
        return np.log(p / (1 - p))


class Temperature:
    """Single-parameter scaling of an existing logit. Cannot fix a shifted prior,
    only a too-sharp/too-flat one -- included to show that difference."""
    name = "temperature"
    def fit(self, s, y):
        from scipy.optimize import minimize_scalar
        def nll(t):
            l = s / max(t, 1e-3)
            return float(np.mean(np.log1p(np.exp(-l * (2 * y - 1)))))
        self.t = float(minimize_scalar(nll, bounds=(1e-2, 1e2), method="bounded").x)
        return self
    def llr(self, s):
        return s / self.t


CALIBRATORS = [Identity, Platt, Isotonic, Temperature]


# ------------------------------------------------------------------ fusion ---
class MeanProb:
    """What the pipeline does today: weighted mean of RAW probabilities."""
    name = "weighted mean of raw probs (current pipeline)"
    def __init__(self, w=None): self.w = w
    def fit(self, X, y):
        if self.w is None:
            self.w = np.ones(X.shape[1]) / X.shape[1]
        return self
    def score(self, X): return X @ self.w


class EqualLLR:
    """Unweighted sum of calibrated LLRs -- the naive-Bayes combination. Optimal only
    if the detectors are conditionally independent, which they are not."""
    name = "equal-weight sum of calibrated LLRs"
    def fit(self, X, y): return self
    def score(self, X): return X.sum(axis=1)


class LogRegFusion:
    """Calibrated linear fusion: L = b + sum w_i * LLR_i, weights learned on dev.
    L2-regularised because the dev set is small relative to the freedom available."""
    name = "logistic fusion (L2)"
    def __init__(self, C=1.0): self.C = C
    def fit(self, X, y):
        from sklearn.linear_model import LogisticRegression
        self.m = LogisticRegression(C=self.C, max_iter=2000).fit(X, y)
        self.w, self.b = self.m.coef_[0], self.m.intercept_[0]
        return self
    def score(self, X): return X @ self.w + self.b


class MLPFusion:
    """The nonlinear arm. Deliberately small and strongly regularised. The literature
    warns this class wins in-domain and loses under distribution shift, which is the
    regime we actually care about -- included to measure that, not to adopt it."""
    name = "MLP fusion (8 hidden, alpha=1.0)"
    def fit(self, X, y):
        from sklearn.neural_network import MLPClassifier
        self.m = MLPClassifier((8,), alpha=1.0, max_iter=3000, random_state=0).fit(X, y)
        return self
    def score(self, X):
        p = np.clip(self.m.predict_proba(X)[:, 1], EPS, 1 - EPS)
        return np.log(p / (1 - p))


class GBFusion:
    name = "gradient boosting (depth 2)"
    def fit(self, X, y):
        from sklearn.ensemble import GradientBoostingClassifier
        self.m = GradientBoostingClassifier(max_depth=2, n_estimators=60,
                                            random_state=0).fit(X, y)
        return self
    def score(self, X):
        p = np.clip(self.m.predict_proba(X)[:, 1], EPS, 1 - EPS)
        return np.log(p / (1 - p))


def load_scores(args):
    """Join every model's per-clip score on the clip path. Returns rows + matrix."""
    tabs = {}
    for f, keys in ((REPO / "research/pipeline_scores.jsonl",
                     ("indic", "dhwani", "customDeepfake")),
                    (REPO / "research/prosody_scores.jsonl", ("prosody",))):
        if not f.exists():
            continue
        for line in open(f):
            r = json.loads(line)
            t = tabs.setdefault(r["path"], dict(r))
            for k in keys:
                if r.get(k) is not None:
                    t[k] = r[k]
    # our research models, already scored, higher = BONAFIDE -> flip to spoof-evidence
    for f, key, flip in ((WT / "results/spectra_scores_preemph.jsonl", "spectra", True),
                         (WT / "results/stage_a_scores.jsonl", "stageA", True),
                         (WT / "results/iv15_scores.jsonl", "iv15", False)):
        if not f.exists():
            continue
        for line in open(f):
            r = json.loads(line)
            t = tabs.get(r["path"])
            if t is None:
                continue
            t[key] = (-r["logit_bonafide"]) if flip else r["p_spoof"]
    return tabs


MODELS = ["indic", "dhwani", "customDeepfake", "prosody", "iv15", "spectra", "stageA"]
L4 = {"Hindi", "Tamil", "Telugu", "Malayalam"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage", default="individual")
    a = ap.parse_args()
    tabs = load_scores(a)
    rows = list(tabs.values())
    have = [m for m in MODELS if sum(r.get(m) is not None for r in rows) > 1000]
    print(f"clips joined: {len(rows)}   models with scores: {have}\n")
    cov = {m: sum(r.get(m) is not None for r in rows) for m in MODELS}
    print("coverage:", {k: v for k, v in cov.items()})

    # every column is SPOOF-evidence (higher = more likely spoof); bonafide label = 0
    def col(m, subset): return np.array([r[m] for r in subset], dtype=float)

    dev = [r for r in rows if r.get("split") == "dev" and all(r.get(m) is not None for m in have)]
    print(f"\ndev clips usable for calibration/fusion: {len(dev)} "
          f"(genuine {sum(r['label']==0 for r in dev)}, spoof {sum(r['label']==1 for r in dev)})")

    print("\n=== PHASE 10/12: each model ALONE on dev (its own contract, no calibration) ===")
    print(f"  {'model':16}{'EER':>8}{'AUC':>9}{'C_llr':>9}{'minCllr':>9}{'cal loss':>10}{'ECE':>8}")
    for m in have:
        s = col(m, dev); y = np.array([r["label"] for r in dev])
        # evidence for GENUINE = -spoof evidence
        e, _ = eer(-s[y == 0], -s[y == 1]); u = auc(-s[y == 0], -s[y == 1])
        p = np.clip(s, EPS, 1 - EPS) if s.min() >= 0 and s.max() <= 1 else None
        if p is not None:
            llr = np.log(p / (1 - p))
        else:
            llr = s
        c = cllr(-llr[y == 0], -llr[y == 1]); mc = min_cllr(-llr[y == 0], -llr[y == 1])
        ee = ece(1 - np.clip(p if p is not None else 1/(1+np.exp(-s)), 0, 1), 1 - y)
        print(f"  {m:16}{e:>8.2f}{u:>9.4f}{c:>9.3f}{mc:>9.3f}{c-mc:>10.3f}{ee:>8.3f}")
    print("\n  C_llr - minCllr is the part of the loss that is PURELY bad calibration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
