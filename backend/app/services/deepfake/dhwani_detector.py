import os
import logging
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from app.services.deepfake.preprocessing import load_and_preprocess_audio, build_windows
from app.services.deepfake.schemas import DhwaniPrediction

logger = logging.getLogger(__name__)

class DeepfakeUnavailable(RuntimeError):
    """Raised when the deepfake model is not available or properly configured."""
    pass

class DhwaniDetector:
    def __init__(self):
        self.model_path = os.getenv("DHWANI_MODEL_PATH")
        self.execution_provider = os.getenv("DHWANI_EXECUTION_PROVIDER", "CPUExecutionProvider")
        self.window_seconds = float(os.getenv("DHWANI_WINDOW_SECONDS", "3.0"))
        self.hop_seconds = float(os.getenv("DHWANI_HOP_SECONDS", "1.5"))
        self.sample_rate = 16000
        
        self.session = None
        self.input_name = None
        self.output_name = None

        if not self.model_path or not os.path.exists(self.model_path):
            raise DeepfakeUnavailable(f"Dhwani model not found at path: {self.model_path}")
        
        if ort is None:
            raise DeepfakeUnavailable("onnxruntime is not installed.")

        try:
            self.session = ort.InferenceSession(self.model_path, providers=[self.execution_provider])
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            logger.info(f"Dhwani model loaded from {self.model_path} using {self.execution_provider}")
        except Exception as e:
            raise DeepfakeUnavailable(f"Failed to initialize ONNX session: {e}") from e

    def predict(self, audio_bytes: bytes) -> DhwaniPrediction:
        if self.session is None:
            raise DeepfakeUnavailable("Model session not initialized.")
        
        # 1. Preprocess
        audio_data = load_and_preprocess_audio(audio_bytes, target_sr=self.sample_rate)
        
        # 2. Windowing
        windows = build_windows(audio_data, self.window_seconds, self.hop_seconds, self.sample_rate)
        
        if len(windows) == 0:
            raise ValueError("Audio segment too short to build any windows.")
            
        # 3. Inference
        window_probs = []
        for w in windows:
            # Model may expect shape (batch, length) or (batch, channels, length)
            # Typically AASIST/XLS-R expects (batch, length) for 1D convolution
            input_tensor = np.expand_dims(w, axis=0) # shape: (1, 48000)
            
            try:
                outputs = self.session.run([self.output_name], {self.input_name: input_tensor})
            except Exception as e:
                logger.error(f"Inference failure: {e}")
                raise ValueError(f"Inference failure: {e}") from e
                
            # output typically logits or probabilities. Assuming probabilities for class 1 (fake) 
            # or logits shape (1, 2) where class 1 is fake.
            output_val = outputs[0]
            if len(output_val.shape) == 2 and output_val.shape[1] > 1:
                # Logits, apply softmax
                exp_vals = np.exp(output_val - np.max(output_val, axis=1, keepdims=True))
                probs = exp_vals / np.sum(exp_vals, axis=1, keepdims=True)
                fake_prob = float(probs[0, 1])
            else:
                # Assuming output is directly probability
                fake_prob = float(output_val[0]) if output_val.size == 1 else float(output_val[0, 0])
                
            window_probs.append(fake_prob)

        # 4. Pooling
        # Max-ish pooling (90th percentile) as done in existing implementation
        pooled_prob = float(np.quantile(window_probs, 0.9)) if len(window_probs) > 1 else float(window_probs[0])
        
        prediction_label = "SYNTHETIC" if pooled_prob > 0.5 else "GENUINE"

        return DhwaniPrediction(
            spoof_probability=round(pooled_prob, 4),
            deepfake_probability=round(pooled_prob, 4),
            prediction=prediction_label,
            model="dhwani",
            windows_scored=len(window_probs),
            window_probabilities=[round(p, 4) for p in window_probs],
            sample_rate=self.sample_rate,
            audio_seconds=round(len(audio_data) / self.sample_rate, 2),
            available=True
        )

# Singleton pattern for warm-up
_DETECTOR_INSTANCE = None

def load_detector() -> DhwaniDetector:
    global _DETECTOR_INSTANCE
    if _DETECTOR_INSTANCE is None:
        _DETECTOR_INSTANCE = DhwaniDetector()
    return _DETECTOR_INSTANCE

def get_detector() -> DhwaniDetector:
    return _DETECTOR_INSTANCE
