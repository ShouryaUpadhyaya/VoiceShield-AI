import whisper
import torch
import os

class WhisperTranscriber:
    def __init__(self, model_size="base", device=None):
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        print(f"Loading Whisper model ({model_size}) on {self.device}...")
        self.model = whisper.load_model(model_size, device=self.device)
        
    def transcribe(self, audio_path):
        """Transcribes the given audio file and returns the text and language."""
        result = self.model.transcribe(audio_path)
        return {
            "text": result["text"].strip(),
            "language": result["language"],
            "segments": result["segments"]
        }
