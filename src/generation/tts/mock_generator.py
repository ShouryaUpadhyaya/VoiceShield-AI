import numpy as np
from src.generation.base import BaseGenerator

class MockGenerator(BaseGenerator):
    def __init__(self, config):
        super().__init__(config)
        self.sample_rate = config.get("output_sample_rate", 16000)
        
    def load_model(self):
        print(f"[{self.model_name}] Loading mock model...")
        self.is_loaded = True
        
    def prepare_input(self, original_metadata, transcript):
        # We don't need real inputs for the mock
        return {"duration": original_metadata.get("duration_seconds", 5.0)}
        
    def generate(self, prepared_input, parameters):
        if not self.is_loaded:
            self.load_model()
            
        print(f"[{self.model_name}] Generating mock audio...")
        duration = min(prepared_input["duration"], 10.0) # Cap at 10s for mock
        t = np.linspace(0, duration, int(self.sample_rate * duration), endpoint=False)
        # Generate a simple 440Hz sine wave as mock audio
        waveform = 0.5 * np.sin(2 * np.pi * 440 * t)
        
        # Convert to int16
        waveform = np.int16(waveform * 32767)
        return waveform
        
    def postprocess(self, waveform, parameters):
        return waveform
