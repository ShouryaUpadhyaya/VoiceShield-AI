import numpy as np
import scipy.signal as signal

def apply_bandwidth_limitation(waveform, sample_rate, low_cutoff=300, high_cutoff=3400):
    """Applies a bandpass filter typical of telephone bandwidth (300-3400 Hz)."""
    nyq = 0.5 * sample_rate
    low = low_cutoff / nyq
    high = high_cutoff / nyq
    
    # Check if high is valid
    if high >= 1.0:
        high = 0.99
        
    b, a = signal.butter(4, [low, high], btype='band')
    # Use lfilter instead of filtfilt to simulate causal filtering, but filtfilt is fine for simplicity
    filtered = signal.filtfilt(b, a, waveform)
    return filtered

def apply_resample_8k(waveform, sample_rate):
    """Resamples the audio to 8kHz to simulate narrowband telephony."""
    if sample_rate <= 8000:
        return waveform, sample_rate
        
    num_samples = int(len(waveform) * 8000 / sample_rate)
    resampled = signal.resample(waveform, num_samples)
    return resampled, 8000

def apply_codec_simulation(waveform, sample_rate):
    """
    Simulates a basic compression codec like mu-law.
    mu-law compression and expansion adds quantization noise characteristic of G.711.
    """
    mu = 255.0
    # Normalize to -1 to 1
    max_val = np.max(np.abs(waveform))
    if max_val == 0:
        return waveform
        
    norm_wave = waveform / max_val
    
    # Compress
    compressed = np.sign(norm_wave) * (np.log(1 + mu * np.abs(norm_wave)) / np.log(1 + mu))
    
    # Quantize to 8 bits
    quantized = np.round(compressed * 128) / 128
    
    # Expand
    expanded = np.sign(quantized) * (1 / mu) * ((1 + mu) ** np.abs(quantized) - 1)
    
    return expanded * max_val

def add_mild_noise(waveform, sample_rate, snr_db=30):
    """Adds white noise at a specific Signal-to-Noise Ratio (SNR)."""
    signal_power = np.mean(waveform ** 2)
    noise_power = signal_power / (10 ** (snr_db / 10))
    noise = np.random.normal(0, np.sqrt(noise_power), len(waveform))
    return waveform + noise

def process_channel(waveform, sample_rate, operations):
    """
    Applies a list of channel operations.
    Operations is a list of strings from the config.
    """
    current_sr = sample_rate
    
    # Ensure waveform is float for processing
    original_dtype = waveform.dtype
    waveform = waveform.astype(np.float64)
    
    for op in operations:
        if op == "bandwidth_limitation":
            waveform = apply_bandwidth_limitation(waveform, current_sr)
        elif op == "resample_8k":
            waveform, current_sr = apply_resample_8k(waveform, current_sr)
        elif op == "codec_simulation":
            waveform = apply_codec_simulation(waveform, current_sr)
        elif op == "mild_noise":
            waveform = add_mild_noise(waveform, current_sr)
        else:
            print(f"Warning: Unknown channel operation '{op}'")
            
    # Clip and convert back to original dtype
    if np.issubdtype(original_dtype, np.integer):
        max_val = np.iinfo(original_dtype).max
        min_val = np.iinfo(original_dtype).min
        waveform = np.clip(waveform, min_val, max_val)
        
    return waveform.astype(original_dtype), current_sr
