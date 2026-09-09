import io
from unittest.mock import patch
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from ml.server.app import app
from ml.pipeline.fusion import DEFAULT_WEIGHTS, ENV_KEYS

client = TestClient(app)  # No lifespan: unit tests do not download checkpoints.


@pytest.fixture(autouse=True)
def weights(monkeypatch):
    for key, value in DEFAULT_WEIGHTS.items():
        monkeypatch.setenv(ENV_KEYS[key], str(value))


def wav(seconds=3):
    buf = io.BytesIO()
    sf.write(buf, np.zeros(int(16000 * seconds)), 16000, format="WAV")
    return buf.getvalue()


def test_get_models():
    response = client.get("/api/models")
    assert response.status_code == 200
    assert "indic" in response.json()["models"]


def test_config_roundtrip():
    weights = {"indic": .5, "dhwani": .5, "customDeepfake": 0, "prosody": 0}
    response = client.put("/api/config/fusion", json={"weights": weights})
    assert response.status_code == 200
    assert client.get("/api/config/fusion").json()["weights"] == weights


def test_partial_config_is_not_merged_with_stale_weights():
    response = client.put("/api/config/fusion", json={"weights": {"indic": 1}})
    assert response.status_code == 400
    assert client.get("/api/config/fusion").json()["weights"] == DEFAULT_WEIGHTS


def test_bad_file_rejected():
    response = client.post("/api/inference/pipeline", files={"audio": ("bad.wav", b"invalid", "audio/wav")})
    assert response.status_code == 400


def test_silent_upload_returns_unknown():
    response = client.post("/api/inference/pipeline", files={"audio": ("silence.wav", wav(), "audio/wav")})
    assert response.status_code == 200
    assert response.json()["result"]["risk"]["score"] is None


def test_long_upload_scores_every_window():
    response = client.post("/api/inference/pipeline", files={"audio": ("long.wav", wav(7), "audio/wav")})
    assert response.status_code == 200
    result = response.json()["result"]
    assert len(result["windows"]) == 3
    assert result["audio"]["duration_ms"] == 7000
    assert result["call_summary"]["unscored_windows"] == 3
    assert result["risk"]["score"] is None


def test_single_route_calls_adapter():
    with patch("ml.server.api.indic_adapter.is_loaded", return_value=True), patch("ml.server.api.indic_adapter.run", return_value={"synthetic_probability": .8}):
        response = client.post("/api/inference/indic", files={"audio": ("clip.wav", wav(), "audio/wav")})
    assert response.status_code == 200
    assert response.json()["result"]["synthetic_probability"] == .8


def test_prosody_only_is_not_ready():
    with patch("ml.server.health.dhwani_adapter.is_loaded", return_value=False), patch("ml.server.health.deepfake_adapter.is_loaded", return_value=False), patch("ml.server.health.indic_adapter.is_loaded", return_value=False), patch("ml.server.health.prosody_adapter.is_loaded", return_value=True):
        response = client.get("/ready")
    assert response.status_code == 503
