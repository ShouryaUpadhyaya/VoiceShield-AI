from pydantic import BaseModel
from typing import List, Optional

class DhwaniPrediction(BaseModel):
    spoof_probability: float
    deepfake_probability: float  # Alias to maintain backward compatibility with risk engine
    prediction: str              # e.g., "SYNTHETIC", "GENUINE"
    model: str                   # e.g., "dhwani"
    windows_scored: int
    window_probabilities: List[float]
    sample_rate: int
    audio_seconds: float
    available: bool = True
