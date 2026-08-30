import torch
import numpy as np
import scipy.io.wavfile as wavfile
import librosa
from transformers import SpeechT5HifiGan
from src.generation.base import BaseGenerator

class HiFiGANGenerator(BaseGenerator):
    def __init__(self, config):
        super().__init__(config)
        self.sample_rate = 16000
        
    def load_model(self):
        print(f"[{self.model_name}] Loading HiFi-GAN model on {self.device}...")
        self.vocoder = SpeechT5HifiGan.from_pretrained("microsoft/speecht5_hifigan").to(self.device)
        self.is_loaded = True
        
    def prepare_input(self, original_metadata, transcript):
        # We need to extract mel spectrograms from the original audio
        # For simplicity, we'll use librosa to extract a basic mel spectrogram
        # and adapt it for the vocoder.
        audio_path = original_metadata["original_path"]
        y, sr = librosa.load(audio_path, sr=self.sample_rate)
        
        # SpeechT5 HiFiGAN expects log-mel spectrograms of shape (batch, sequence_length, num_mel_bins)
        # 80 mel bins, 25ms window, 10ms hop
        n_fft = int(0.025 * self.sample_rate)
        hop_length = int(0.010 * self.sample_rate)
        
        mel = librosa.feature.melspectrogram(
            y=y, sr=self.sample_rate, n_fft=n_fft, hop_length=hop_length, n_mels=80, fmin=0, fmax=8000
        )
        # Log mel
        log_mel = librosa.power_to_db(mel, ref=np.max)
        
        # Shape to (1, seq_len, 80)
        log_mel = log_mel.T
        log_mel = np.expand_dims(log_mel, axis=0)
        
        inputs = torch.tensor(log_mel, dtype=torch.float32).to(self.device)
        return inputs
        
    def generate(self, prepared_input, parameters):
        if not self.is_loaded:
            self.load_model()
            
        print(f"[{self.model_name}] Generating vocoded audio...")
        with torch.no_grad():
            speech = self.vocoder(prepared_input)
            
        waveform = speech.cpu().numpy().squeeze()
        waveform = np.clip(waveform, -1.0, 1.0)
        waveform = np.int16(waveform * 32767)
        return waveform
        
    def postprocess(self, waveform, parameters):
        return waveform
