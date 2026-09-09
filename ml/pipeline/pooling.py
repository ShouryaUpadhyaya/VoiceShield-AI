"""Descriptive upload pooling over the same three-second windows as live audio."""
from copy import deepcopy
from ml.pipeline.fusion import valid_score


def pool_responses(windows):
    if len(windows) == 1:
        return windows[0]
    result = deepcopy(windows[0])
    usable = [w for w in windows if valid_score(w["signals"]["deepfake_probability"])]
    mean = sum(w["signals"]["deepfake_probability"] for w in usable) / len(usable) if usable else None
    result["signals"] = {"deepfake_probability": round(mean, 4) if mean is not None else None}
    result["inference_ms"] = sum(w["inference_ms"] for w in windows)
    result["audio"]["duration_ms"] = sum(w["audio"]["duration_ms"] for w in windows)
    result["real_time_factor"] = result["inference_ms"] / max(1, result["audio"]["duration_ms"])
    result["window_seq"] = None
    result["audio_quality"] = {"eligible": bool(usable), "scored_windows": len(usable), "total_windows": len(windows)}
    result["model_errors"] = {f"{i}:{k}": v for i, w in enumerate(windows) for k, v in w["model_errors"].items()}
    reasons = sorted({reason for w in windows for reason in w["risk"]["reasons"]})
    if any(w["risk"]["level"] == "HIGH" for w in usable):
        reasons.append("suspicious_segment")
    result["risk"] = {**result["risk"], "score": round(mean*100, 1) if mean is not None else None,
                      "status": "insufficient_evidence" if mean is None else "review" if reasons else "scored",
                      "level": "UNKNOWN" if mean is None else "REVIEW" if reasons else "HIGH" if mean >= .75 else "MEDIUM" if mean >= .4 else "LOW",
                      "reasons": reasons,
                      "recommended_action": "COLLECT_MORE_AUDIO" if mean is None else "SECONDARY_VERIFICATION" if reasons or mean >= .4 else "CONTINUE_WITH_CAUTION"}
    result["fusion"] = None if mean is None else {
        "aiGeneratedScore": round(mean, 4), "method": "mean_valid_windows", "calibrated": False,
        "weights": {}, "contributions": {}, "policy_version": "sih-evidence-v1"}
    for name in result["detectors"]:
        observations = [w["detectors"][name] for w in usable if valid_score(w["detectors"][name]["score"])]
        result["detectors"][name] = {"score": sum(x["score"] for x in observations)/len(observations) if observations else None,
                                      "weight": sum(x["weight"] for x in observations)/len(observations) if observations else 0,
                                      "status": "complete" if len(observations) == len(windows) else "partial" if observations else "unavailable"}
        if usable:
            for field in ("weights", "contributions"):
                result["fusion"][field][name] = sum(w["fusion"][field].get(name, 0) for w in usable) / len(usable)
    result["call_summary"] = {"mean_evidence_pct": round(mean*100, 1) if mean is not None else None,
                              "peak_evidence_pct": max(w["risk"]["score"] for w in usable) if usable else None,
                              "scored_windows": len(usable), "unscored_windows": len(windows)-len(usable),
                              "calibrated": False}
    result["windows"] = windows
    return result
