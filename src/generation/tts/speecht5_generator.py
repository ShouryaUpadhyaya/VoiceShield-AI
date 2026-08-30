import torch
from transformers import SpeechT5Processor, SpeechT5ForTextToSpeech, SpeechT5HifiGan
from datasets import load_dataset
import numpy as np
from src.generation.base import BaseGenerator

class SpeechT5Generator(BaseGenerator):
    def __init__(self, config):
        super().__init__(config)
        self.sample_rate = 16000 # SpeechT5 output SR
        
    def load_model(self):
        print(f"[{self.model_name}] Loading SpeechT5 TTS model on {self.device}...")
        self.processor = SpeechT5Processor.from_pretrained("microsoft/speecht5_tts")
        self.model = SpeechT5ForTextToSpeech.from_pretrained("microsoft/speecht5_tts").to(self.device)
        self.vocoder = SpeechT5HifiGan.from_pretrained("microsoft/speecht5_hifigan").to(self.device)
        
        # Generate a deterministic synthetic x-vector for default voice to bypass dataset load issues
        print(f"[{self.model_name}] Initializing speaker embeddings...")
        np.random.seed(42)
        self.speaker_embeddings = torch.tensor(np.random.normal(0, 0.1, (1, 512)), dtype=torch.float32).to(self.device)
        self.is_loaded = True
        
    def prepare_input(self, original_metadata, transcript):
        text = transcript if transcript else "Hello, this is a default transcript because none was provided."
        # Truncate text to avoid SpeechT5 sequence length limits
        if len(text) > 300:
            text = text[:300] + "..."
            
        # SpeechT5 is primarily English, so we might need to filter out unsupported chars
        inputs = self.processor(text=text, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        return inputs
        
    def generate(self, prepared_input, parameters):
        if not self.is_loaded:
            self.load_model()
            
        print(f"[{self.model_name}] Generating TTS audio...")
        with torch.no_grad():
            speech = self.model.generate_speech(prepared_input["input_ids"], self.speaker_embeddings, vocoder=self.vocoder)
            
        # Output is a 1D tensor
        waveform = speech.cpu().numpy()
        
        # Convert float32 [-1, 1] to int16
        waveform = np.clip(waveform, -1.0, 1.0)
        waveform = np.int16(waveform * 32767)
        return waveform
        
    def postprocess(self, waveform, parameters):
        return waveform
