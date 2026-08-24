import random

def verify_speaker(filename: str, audio_bytes: bytes, claimed_identity: str = "CEO") -> float:
    """
    Mock Speaker Verification Model for Phase 2.
    Returns a similarity score between 0.0 (no match) and 1.0 (perfect match).
    """
    if "unregistered" in filename.lower():
        return round(random.uniform(0.1, 0.35), 2)
    elif "ceo" in filename.lower() or "trusted" in filename.lower():
        return round(random.uniform(0.75, 0.95), 2)
    return round(random.uniform(0.4, 0.8), 2)
