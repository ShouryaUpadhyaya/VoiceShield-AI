import torch
import numpy as np
from transformers import VitsModel, AutoTokenizer
from src.generation.base import BaseGenerator

class MMSGenerator(BaseGenerator):
    def __init__(self, config):
        super().__init__(config)
        self.sample_rate = 16000 # MMS TTS output SR is actually 16000
        
    def load_model(self):
        print(f"[{self.model_name}] Loading MMS TTS (Hindi) model on {self.device}...")
        self.model = VitsModel.from_pretrained("facebook/mms-tts-hin").to(self.device)
        self.tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-hin")
        self.sample_rate = self.model.config.sampling_rate
        self.is_loaded = True
        
    def prepare_input(self, original_metadata, transcript):
        text = transcript if transcript else "नमस्ते, यह एक डिफ़ॉल्ट संदेश है।"
        # Truncate text to avoid long sequences if necessary
        if len(text) > 300:
            text = text[:300] + "..."
            
        inputs = self.tokenizer(text, return_tensors="pt")
        
        # If tokenizer stripped all characters (e.g. English text), fallback to default
        if inputs["input_ids"].shape[1] == 0:
            fallback = "नमस्ते, यह एक डिफ़ॉल्ट संदेश है।"
            inputs = self.tokenizer(fallback, return_tensors="pt")
            
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        return inputs
        
    def generate(self, prepared_input, parameters):
        if not self.is_loaded:
            self.load_model()
            
        print(f"[{self.model_name}] Generating TTS audio...")
        with torch.no_grad():
            output = self.model(**prepared_input).waveform
            
        waveform = output.cpu().numpy().squeeze()
        
        # Normalize and convert float32 to int16
        waveform = np.clip(waveform, -1.0, 1.0)
        waveform = np.int16(waveform * 32767)
        return waveform
        
    def postprocess(self, waveform, parameters):
        return waveform
