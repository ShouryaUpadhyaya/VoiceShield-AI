import io
import os
import numpy as np
import soundfile as sf
import scipy.signal

def load_and_preprocess_audio(audio_bytes: bytes, target_sr: int = 16000) -> np.ndarray:
    """
    Decodes audio bytes, converts to mono, resamples to target_sr if needed,
    and returns a float32 numpy array.
    """
    try:
        with io.BytesIO(audio_bytes) as audio_file:
            data, samplerate = sf.read(audio_file)
    except sf.LibsndfileError as e:
        raise ValueError(f"Unable to decode audio payload: {e}") from e
    except Exception as e:
        raise ValueError(f"Invalid audio format: {e}") from e

    if len(data) == 0:
        raise ValueError("Audio file is empty")

    # Convert to mono if stereo
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)

    # Resample if sample rate doesn't match
    if samplerate != target_sr:
        num_samples = int(len(data) * target_sr / samplerate)
        data = scipy.signal.resample(data, num_samples)

    # Convert to float32
    data = data.astype(np.float32)
    
    # Remove NaN/Inf
    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)

    # Normalize roughly to [-1.0, 1.0] if not already
    max_val = np.max(np.abs(data))
    if max_val > 0 and max_val > 1.0:
        data = data / max_val

    return data

def build_windows(audio_data: np.ndarray, window_duration: float, hop_duration: float, sample_rate: int = 16000) -> np.ndarray:
    """
    Splits the 1D audio array into overlapping windows.
    Pads with zeros if the audio is shorter than a single window.
    """
    window_samples = int(window_duration * sample_rate)
    hop_samples = int(hop_duration * sample_rate)

    if len(audio_data) < window_samples:
        # Pad shorter audio
        padding = window_samples - len(audio_data)
        audio_data = np.pad(audio_data, (0, padding), mode='constant')
        return np.expand_dims(audio_data, axis=0)

    windows = []
    start = 0
    while start + window_samples <= len(audio_data):
        windows.append(audio_data[start:start + window_samples])
        start += hop_samples

    # If the last window didn't perfectly align and there is significant remainder, pad the rest
    if start < len(audio_data):
        remainder = audio_data[start:]
        if len(remainder) > window_samples * 0.1: # Only pad if remainder > 10% of window
            padded_remainder = np.pad(remainder, (0, window_samples - len(remainder)), mode='constant')
            windows.append(padded_remainder)

    if not windows:
        return np.array([])

    return np.stack(windows)
