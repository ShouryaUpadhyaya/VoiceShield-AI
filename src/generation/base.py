from abc import ABC, abstractmethod
import os

class BaseGenerator(ABC):
    def __init__(self, config):
        self.config = config
        self.model_name = config.get("name")
        self.family = config.get("family")
        self.device = config.get("device", "cpu")
        self.is_loaded = False
        
    @abstractmethod
    def load_model(self):
        """Loads the model weights into memory (CPU/GPU)."""
        pass

    @abstractmethod
    def prepare_input(self, original_metadata, transcript):
        """Prepares input data for the model (e.g., text for TTS, audio for VC)."""
        pass

    @abstractmethod
    def generate(self, prepared_input, parameters):
        """Generates the synthetic audio waveform."""
        pass

    @abstractmethod
    def postprocess(self, waveform, parameters):
        """Applies any model-specific post-processing."""
        pass

    def cleanup(self):
        """Releases GPU memory if needed."""
        self.is_loaded = False
        # Optional default implementation to clear CUDA cache etc.
