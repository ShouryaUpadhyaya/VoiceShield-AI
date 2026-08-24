import random

def analyze_prosody(filename: str, audio_bytes: bytes) -> dict:
    """
    Mock Prosody & Behavioral Analysis for Phase 2.
    Returns anomaly scores. Higher score means more unnatural speech.
    """
    is_robotic = "robotic" in filename.lower() or "fake" in filename.lower()
    
    pitch_anomaly = round(random.uniform(0.6, 0.9) if is_robotic else random.uniform(0.1, 0.4), 2)
    pause_anomaly = round(random.uniform(0.6, 0.9) if is_robotic else random.uniform(0.1, 0.4), 2)
    rhythm_anomaly = round(random.uniform(0.6, 0.9) if is_robotic else random.uniform(0.1, 0.4), 2)
    
    overall_prosody_risk = round((pitch_anomaly + pause_anomaly + rhythm_anomaly) / 3.0, 2)
    
    return {
        "pitch_anomaly": pitch_anomaly,
        "pause_anomaly": pause_anomaly,
        "rhythm_anomaly": rhythm_anomaly,
        "overall_prosody_risk": overall_prosody_risk
    }
