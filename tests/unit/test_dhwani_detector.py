import os
import io
import pytest
import numpy as np
import soundfile as sf
import scipy.signal
from unittest.mock import patch, MagicMock

# Set env var before importing
os.environ["DHWANI_MODEL_PATH"] = os.path.join(os.path.dirname(__file__), "dummy_dhwani.onnx")
os.environ["DHWANI_EXECUTION_PROVIDER"] = "CPUExecutionProvider"
os.environ["DHWANI_WINDOW_SECONDS"] = "3.0"
os.environ["DHWANI_HOP_SECONDS"] = "1.5"

from app.services.deepfake.dhwani_detector import load_detector, DhwaniDetector, DeepfakeUnavailable
from app.api.routes.audio import router
from fastapi.testclient import TestClient
from fastapi import FastAPI

app = FastAPI()
app.include_router(router, prefix="/api")
client = TestClient(app)

def create_audio_bytes(duration_sec: float, sr: int = 16000, channels: int = 1) -> bytes:
    samples = int(duration_sec * sr)
    data = np.random.randn(samples, channels).astype(np.float32) if channels > 1 else np.random.randn(samples).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, data, sr, format='WAV')
    return buf.getvalue()

@pytest.fixture(scope="module")
def dummy_onnx():
    path = os.environ["DHWANI_MODEL_PATH"]
    if not os.path.exists(path):
        pytest.skip(f"Dummy ONNX model not found at {path}. Run create_dummy_onnx.py first.")
    return path

class TestDhwaniDetector:
    
    def test_1_model_loading(self, dummy_onnx):
        """Test 1 — Model loading: model exists → model loads successfully"""
        detector = DhwaniDetector()
        assert detector.session is not None
        assert detector.input_name == "input"

    def test_2_valid_genuine_audio(self, dummy_onnx):
        """Test 2 — Valid genuine audio: 16kHz mono audio → inference returns valid result"""
        detector = DhwaniDetector()
        audio_bytes = create_audio_bytes(3.0, 16000, 1)
        result = detector.predict(audio_bytes)
        assert result.available
        assert 0.0 <= result.spoof_probability <= 1.0

    def test_3_synthetic_cloned_sample(self, dummy_onnx):
        """Test 3 — Synthetic/cloned sample: AI-generated sample → inference returns valid result"""
        # We can't guarantee 'fake' classification without a real model, but we check if it runs.
        detector = DhwaniDetector()
        audio_bytes = create_audio_bytes(3.0, 16000, 1)
        result = detector.predict(audio_bytes)
        assert result.available
        assert isinstance(result.prediction, str)
        assert result.prediction in ["SYNTHETIC", "GENUINE"]

    def test_4_resampling(self, dummy_onnx):
        """Test 4 — Resampling: 8kHz input → preprocessing → 16kHz model input"""
        detector = DhwaniDetector()
        audio_bytes = create_audio_bytes(3.0, 8000, 1) # 8kHz
        result = detector.predict(audio_bytes)
        # Verify it processed as 16kHz (3 seconds = 48000 samples = 1 window of 3s)
        assert result.sample_rate == 16000

    def test_5_stereo_input(self, dummy_onnx):
        """Test 5 — Stereo input: stereo audio → mono conversion"""
        detector = DhwaniDetector()
        audio_bytes = create_audio_bytes(3.0, 16000, 2) # Stereo
        result = detector.predict(audio_bytes)
        assert result.available

    def test_6_short_audio(self, dummy_onnx):
        """Test 6 — Short audio: short audio → correctly padded/handled"""
        detector = DhwaniDetector()
        audio_bytes = create_audio_bytes(1.0, 16000, 1) # 1 second (too short for 3s window)
        result = detector.predict(audio_bytes)
        assert result.windows_scored == 1
        assert result.audio_seconds == 1.0

    def test_7_long_audio(self, dummy_onnx):
        """Test 7 — Long audio: long audio → correct windowing/trimming"""
        detector = DhwaniDetector()
        audio_bytes = create_audio_bytes(6.0, 16000, 1) # 6 seconds (should create multiple windows)
        result = detector.predict(audio_bytes)
        # 6 seconds with 3s window and 1.5s hop = 3 full windows + 1 padded remainder = 4 windows
        assert result.windows_scored == 4

    def test_8_invalid_audio(self, dummy_onnx):
        """Test 8 — Invalid audio: corrupt input → clean error"""
        detector = DhwaniDetector()
        with pytest.raises(ValueError, match="Unable to decode audio payload"):
            detector.predict(b"not a valid wav file")

    def test_9_session_reuse(self, dummy_onnx):
        """Test 9 — Session reuse: Verify that the ONNX runtime session is not recreated"""
        detector1 = load_detector()
        detector2 = load_detector()
        assert detector1 is detector2
        assert detector1.session is detector2.session

    @patch("app.api.routes.audio.analyze_deepfake")
    def test_10_api_endpoint(self, mock_analyze):
        """Test 10 — API endpoint: Verify the API returns the expected schema."""
        mock_analyze.return_value = {
            "spoof_probability": 0.91,
            "deepfake_probability": 0.91,
            "prediction": "SYNTHETIC",
            "model": "dhwani",
            "windows_scored": 1,
            "window_probabilities": [0.91],
            "sample_rate": 16000,
            "audio_seconds": 3.0,
            "available": True
        }
        
        audio_bytes = create_audio_bytes(3.0)
        response = client.post(
            "/api/analyze/audio",
            files={"file": ("test.wav", audio_bytes, "audio/wav")}
        )
        assert response.status_code == 200
        data = response.json()
        assert "deepfake_detail" in data
        assert data["deepfake_detail"]["model"] == "dhwani"
        assert data["deepfake_detail"]["prediction"] == "SYNTHETIC"
        assert data["deepfake_detail"]["spoof_probability"] == 0.91
