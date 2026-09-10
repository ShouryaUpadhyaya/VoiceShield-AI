"""Auditable demo risk policy. Scores are not calibrated fraud probabilities."""
from __future__ import annotations

import math
import os
import threading

_config_lock = threading.RLock()

# Best integrated candidate on historical dev EER. Still provisional for live calls.
DEFAULT_WEIGHTS = {"indic": 0.1, "dhwani": 0.8, "customDeepfake": 0.0, "prosody": 0.1}
ENV_KEYS = {"indic": "FUSION_INDIC_WEIGHT", "dhwani": "FUSION_DHWANI_WEIGHT",
            "customDeepfake": "FUSION_CUSTOM_WEIGHT", "prosody": "FUSION_PROSODY_WEIGHT"}


def validate_weights(weights):
    if not isinstance(weights, dict) or set(weights) != set(DEFAULT_WEIGHTS):
        raise ValueError("Provide all four weights: indic, dhwani, customDeepfake, prosody")
    for value in weights.values():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Weights must be finite numbers between 0 and 1")

    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-4):
        raise ValueError("Weights must sum to 1.0")
    return {k: float(weights[k]) for k in DEFAULT_WEIGHTS}


def get_weights():
    with _config_lock:
        return validate_weights({k: float(os.getenv(ENV_KEYS[k], str(v))) for k, v in DEFAULT_WEIGHTS.items()})


def set_weights(weights):
    weights = validate_weights(weights)
    with _config_lock:
        for key, value in weights.items():
            os.environ[ENV_KEYS[key]] = str(value)
    return weights


def valid_score(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 1


def fuse(inference):
    weights = get_weights()
    sources = {"indic": ("indic", "synthetic_probability"), "dhwani": ("dhwani", "synthetic_probability"),
               "customDeepfake": ("custom_deepfake", "deepfake_probability"), "prosody": ("prosody", "overall_prosody_risk")}
    scores, detectors = {}, {}
    for name, (source, key) in sources.items():
        result = inference.get(source)
        value = result.get(key) if isinstance(result, dict) else None
        ok = valid_score(value)
        if ok and name != "prosody":
            scores[name] = float(value)
        detectors[name] = {"score": float(value) if ok else None, "weight": 0.0,
                           "configured_weight": weights[name],
                           "status": "complete" if ok else "invalid" if result is not None else "unavailable",
                           "role": "supporting_evidence" if name == "prosody" else "deepfake_detector"}
    total = sum(weights[k] for k in scores)
    quality = inference.get("audio_quality", {})
    eligible = quality.get("eligible", True)
    fusion = None
    reasons = list(quality.get("reasons", []))
    if total > 0 and eligible:
        effective = {k: weights[k] / total for k in scores if weights[k] > 0}
        value = sum(scores[k] * effective[k] for k in effective)
        for k, w in effective.items():
            detectors[k]["weight"] = w
        fusion = {"aiGeneratedScore": round(value, 4), "method": "weighted_mean",
                  "policy_version": "sih-evidence-v1", "calibrated": False,
                  "weights": effective, "contributions": {k: round(scores[k] * effective[k], 4) for k in effective},
                  "coverage": round(total, 4), "score_spread": round(max(scores.values()) - min(scores.values()), 4)}
        missing = [k for k, w in weights.items() if w > 0 and k not in scores]
        if missing:
            reasons.append("missing_detectors:" + ",".join(missing))
        if fusion["score_spread"] >= .5:
            reasons.append("detector_disagreement")
        if quality.get("warnings"):
            reasons.extend(quality["warnings"])
        status = "review" if reasons else "scored"
        level = "REVIEW" if reasons else "HIGH" if value >= .75 else "MEDIUM" if value >= .4 else "LOW"
    else:
        value, status, level = None, "insufficient_evidence", "UNKNOWN"
        if eligible:
            reasons.append("no_valid_deepfake_detector")
    risk = {"score": round(100 * value, 1) if value is not None else None,
            "scale": "0-100", "kind": "synthetic_audio_evidence", "calibrated": False,
            "status": status, "level": level, "reasons": reasons,
            "recommended_action": "COLLECT_MORE_AUDIO" if value is None else "SECONDARY_VERIFICATION" if level != "LOW" else "CONTINUE_WITH_CAUTION",
            "interpretation": "Demo evidence index; not the probability of fraud or proof of identity."}
    return fusion, detectors, risk
