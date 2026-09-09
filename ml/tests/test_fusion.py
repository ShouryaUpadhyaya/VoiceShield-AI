import json
import pytest
import numpy as np
from ml.pipeline.results import build_score_response
from ml.pipeline.fusion import DEFAULT_WEIGHTS, ENV_KEYS, validate_weights
from ml.pipeline.inference import run_inference


@pytest.fixture(autouse=True)
def weights(monkeypatch):
    for key, value in {"indic": 1/3, "dhwani": 1/3, "customDeepfake": 1/3, "prosody": 0}.items():
        monkeypatch.setenv(ENV_KEYS[key], str(value))


def result(**kwargs):
    return build_score_response("test", 0, 0, {"total_latency_ms": 10, "real_time_factor": .1, **kwargs})


def test_prosody_alone_cannot_accuse():
    r = result(prosody={"overall_prosody_risk": 1.0})
    assert r["fusion"] is None
    assert r["risk"]["score"] is None
    assert r["risk"]["level"] == "UNKNOWN"


def test_missing_models_are_explicit():
    r = result(indic={"synthetic_probability": .9})
    assert r["risk"]["score"] == 90
    assert r["risk"]["status"] == "review"
    assert r["fusion"]["weights"] == {"indic": 1}
    assert r["detectors"]["indic"]["weight"] == 1


def test_disagreement_requires_review():
    r = result(indic={"synthetic_probability": 1}, dhwani={"synthetic_probability": 0},
               custom_deepfake={"deepfake_probability": 0})
    assert "detector_disagreement" in r["risk"]["reasons"]
    assert r["risk"]["level"] == "REVIEW"
    assert r["risk"]["calibrated"] is False


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -1, 2, True, "0.9"])
def test_invalid_scores_never_enter_fusion(score):
    r = result(indic={"synthetic_probability": score}, dhwani={"synthetic_probability": .2})
    assert r["detectors"]["indic"]["status"] == "invalid"
    assert r["risk"]["score"] == 20
    json.dumps(r["risk"], allow_nan=False)


@pytest.mark.parametrize("audio", [np.zeros(48000), np.full(48000, .1), np.full(48000, np.nan), np.ones(100)])
def test_bad_audio_abstains_without_running_models(monkeypatch, audio):
    def forbidden(*args):
        pytest.fail("Model should not run on invalid audio")
    monkeypatch.setattr("ml.adapters.dhwani.run", forbidden)
    r = build_score_response("test", 0, 0, run_inference(audio, "test", 0))
    assert r["risk"]["score"] is None
    assert r["risk"]["status"] == "insufficient_evidence"
    json.dumps(r, allow_nan=False)


@pytest.mark.parametrize("bad", [{"indic": 1}, {**DEFAULT_WEIGHTS, "indic": float("nan")},
                                 {**DEFAULT_WEIGHTS, "indic": True},
                                 {"indic": .3, "dhwani": .3, "customDeepfake": .3, "prosody": .1}])
def test_invalid_config_rejected(bad):
    with pytest.raises(ValueError):
        validate_weights(bad)


def test_weighted_contributions_sum():
    r = result(indic={"synthetic_probability": .2}, dhwani={"synthetic_probability": .4},
               custom_deepfake={"deepfake_probability": .6}, prosody={"overall_prosody_risk": 1})
    assert r["risk"]["score"] == 40
    assert r["detectors"]["prosody"]["weight"] == 0
    assert sum(r["fusion"]["contributions"].values()) == pytest.approx(.4, abs=1e-4)


def test_default_does_not_replace_failed_primary_with_unvalidated_fallback(monkeypatch):
    for key, value in DEFAULT_WEIGHTS.items():
        monkeypatch.setenv(ENV_KEYS[key], str(value))
    r = result(dhwani={"synthetic_probability": .9}, prosody={"overall_prosody_risk": 1})
    assert r["risk"]["score"] is None
