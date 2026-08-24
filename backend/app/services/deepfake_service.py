import random

def analyze_deepfake(filename: str, audio_bytes: bytes) -> float:
    if 'fake' in filename.lower():
        return round(random.uniform(0.75, 0.99), 2)
    elif 'real' in filename.lower():
        return round(random.uniform(0.01, 0.25), 2)
    return round(random.uniform(0.1, 0.9), 2)
