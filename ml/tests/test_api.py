import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from ml.server.app import app

client = TestClient(app)

def test_get_models():
    response = client.get("/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert "indic" in data["models"]

def test_get_fusion_config():
    response = client.get("/api/config/fusion")
    assert response.status_code == 200
    data = response.json()
    assert "weights" in data

def test_update_fusion_config():
    response = client.put(
        "/api/config/fusion",
        json={"weights": {"indic": 0.5, "dhwani": 0.5, "customDeepfake": 0.0, "prosody": 0.0}}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["weights"]["indic"] == 0.5

def test_update_fusion_config_invalid():
    response = client.put(
        "/api/config/fusion",
        json={"weights": {"indic": 0.9, "dhwani": 0.9, "customDeepfake": 0.0, "prosody": 0.0}}
    )
    assert response.status_code == 400
    assert "sum to 1" in response.json()["detail"]

@patch("ml.server.api.run_single_model")
def test_inference_single(mock_run):
    mock_run.return_value = {"success": True, "result": "mock"}
    response = client.post(
        "/api/inference/indic",
        files={"audio": ("test.wav", b"fakeaudio", "audio/wav")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result"] == "mock"

@patch("ml.server.api.run_pipeline")
def test_inference_pipeline(mock_run):
    mock_run.return_value = {"success": True, "result": "mock_pipeline"}
    response = client.post(
        "/api/inference/pipeline",
        files={"audio": ("test.wav", b"fakeaudio", "audio/wav")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result"] == "mock_pipeline"
