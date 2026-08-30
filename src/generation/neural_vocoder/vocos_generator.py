import torch
import numpy as np
import scipy.io.wavfile as wavfile
import librosa
from vocos import Vocos
from encodec import EncodecModel
from encodec.utils import convert_audio
from src.generation.base import BaseGenerator

class VocosGenerator(BaseGenerator):
    def __init__(self, config):
        super().__init__(config)
        self.sample_rate = 24000
        
    def load_model(self):
        print(f"[{self.model_name}] Loading Encodec and Vocos models on {self.device}...")
        self.encodec = EncodecModel.encodec_model_24khz().to(self.device)
        self.encodec.set_target_bandwidth(6.0)
        
        self.vocos = Vocos.from_pretrained("charactr/vocos-encodec-24khz").to(self.device)
        self.is_loaded = True
        
    def prepare_input(self, original_metadata, transcript):
        audio_path = original_metadata["original_path"]
        # Load audio and convert to 24kHz for Encodec/Vocos
        y, sr = librosa.load(audio_path, sr=24000)
        
        wav = torch.tensor(y, dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(self.device)
        
        # We encode it to get discrete tokens using Encodec
        with torch.no_grad():
            encoded_frames = self.encodec.encode(wav)
            
        return encoded_frames
        
    def generate(self, prepared_input, parameters):
        if not self.is_loaded:
            self.load_model()
            
        print(f"[{self.model_name}] Decoding with Encodec neural vocoder...")
        encoded_frames = prepared_input
        
        with torch.no_grad():
            audio_out = self.encodec.decode(encoded_frames)[0]
            
        waveform = audio_out.cpu().numpy().squeeze()
        
        # Normalize and convert float32 to int16
        waveform = np.clip(waveform, -1.0, 1.0)
        waveform = np.int16(waveform * 32767)
        return waveform
        
    def postprocess(self, waveform, parameters):
        return waveform
