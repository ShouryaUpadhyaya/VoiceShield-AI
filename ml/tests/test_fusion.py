import os
import pytest
from ml.pipeline.results import build_score_response

@pytest.fixture(autouse=True)
def mock_weights(monkeypatch):
    monkeypatch.setenv("FUSION_INDIC_WEIGHT", "0.45")
    monkeypatch.setenv("FUSION_DHWANI_WEIGHT", "0.20")
    monkeypatch.setenv("FUSION_CUSTOM_WEIGHT", "0.20")
    monkeypatch.setenv("FUSION_PROSODY_WEIGHT", "0.15")


def _build_inference_result(indic_score=None, dhwani_score=None, custom_score=None, prosody_score=None):
    return {
        "total_latency_ms": 100,
        "real_time_factor": 0.5,
        "audio_duration_ms": 3000,
        "indic": {"synthetic_probability": indic_score} if indic_score is not None else None,
        "dhwani": {"synthetic_probability": dhwani_score} if dhwani_score is not None else None,
        "custom_deepfake": {"deepfake_probability": custom_score} if custom_score is not None else None,
        "prosody": {"overall_prosody_risk": prosody_score} if prosody_score is not None else None,
        "speaker_verification": None
    }


def test_fusion_equal_scores():
    inference_result = _build_inference_result(0.5, 0.5, 0.5, 0.5)
    resp = build_score_response("sess-1", 1, 0, inference_result)
    
    assert resp["fusion"]["aiGeneratedScore"] == 0.50
    assert resp["signals"]["deepfake_probability"] == 0.50


def test_fusion_indic_high():
    inference_result = _build_inference_result(1.0, 0.0, 0.0, 0.0)
    resp = build_score_response("sess-1", 1, 0, inference_result)
    
    # Only indic is 1.0, weight is 0.45.
    assert resp["fusion"]["aiGeneratedScore"] == 0.45
    assert resp["fusion"]["contributions"]["indic"] == 0.45
    assert resp["fusion"]["contributions"]["dhwani"] == 0.0


def test_fusion_indic_low():
    inference_result = _build_inference_result(0.0, 1.0, 1.0, 1.0)
    resp = build_score_response("sess-1", 1, 0, inference_result)
    
    # Others sum to 0.55
    assert resp["fusion"]["aiGeneratedScore"] == 0.55


def test_fusion_missing_detector():
    # Indic is missing. Weights should re-normalize.
    # Total available weight: 0.20 + 0.20 + 0.15 = 0.55
    # If all others are 1.0, the normalized score should be 1.0
    inference_result = _build_inference_result(None, 1.0, 1.0, 1.0)
    resp = build_score_response("sess-1", 1, 0, inference_result)
    
    assert resp["detectors"]["indic"]["status"] == "unavailable"
    assert resp["detectors"]["indic"]["score"] is None
    assert resp["fusion"]["aiGeneratedScore"] == 1.0
    
    # Normalized weight of dhwani should be 0.20 / 0.55 = 0.3636
    assert resp["fusion"]["weights"]["dhwani"] == pytest.approx(0.20 / 0.55)


def test_fusion_all_missing():
    inference_result = _build_inference_result(None, None, None, None)
    resp = build_score_response("sess-1", 1, 0, inference_result)
    
    assert resp["fusion"] is None
    assert resp["signals"]["deepfake_probability"] is None
