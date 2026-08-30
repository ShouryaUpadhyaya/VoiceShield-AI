"""The audio front end, imported by BOTH training and inference.

The original `main.py` fed RawNet ~108-dim hand-crafted features (MFCC means, mel
means, ZCR, spectral bandwidth, RMS, spectral contrast) while `eval.py` fed raw
96,000-sample waveforms. RawNet is a raw-waveform model, so training and serving
disagreed completely and a model trained by `main.py` could never have been scored
by `eval.py`.

One module, two callers, so the two paths cannot drift again.
"""

from __future__ import annotations

import numpy as np

TARGET_SR = 16_000


def pad(x: np.ndarray, max_len: int) -> np.ndarray:
    """Crop to `max_len`, or tile the signal up to it.

    Tiling rather than zero-padding is the ASVspoof RawNet2 baseline convention, and
    it matters here: zero padding would hand the model long silent stretches, and
    silence is exactly the kind of cue a detector learns instead of synthesis.
    """
    x_len = x.shape[0]
    if x_len >= max_len:
        return x[:max_len]
    num_repeats = int(max_len / x_len) + 1
    return np.tile(x, (1, num_repeats))[:, :max_len][0]


def peak_normalise(y: np.ndarray, target_peak: float = 0.95) -> np.ndarray:
    """Per-utterance gain removal.

    The IndicTTS-Deepfake corpus carries a measured loudness bias -- real audio sits
    ~4.5 dB louder than TTS, enough that peak amplitude alone separates the classes
    at ~0.77 AUC. Normalising denies the model that shortcut. Applied identically at
    train and serve time, or the front ends diverge again.
    """
    peak = float(np.abs(y).max())
    if peak < 1e-9:
        return y.astype(np.float32)
    return (y * (target_peak / peak)).astype(np.float32)


def load_audio(path, target_sr: int = TARGET_SR, normalise: bool = True) -> np.ndarray:
    """Read a file to mono float32 at `target_sr`, optionally peak-normalised."""
    import librosa

    y, sr = librosa.load(str(path), sr=None, mono=True)
    if sr != target_sr:
        y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
    y = np.asarray(y, dtype=np.float32)
    return peak_normalise(y) if normalise else y


def trim_silence(y, sr: int, top_db: float = 40.0):
    """Strip leading and trailing silence.

    This lives in the SHARED front end on purpose. Trimming is a property of the audio
    contract, not of a class: applying it to synthetic clips only would replace one
    silence shortcut with its mirror image, and applying it in training but not at
    inference would mean the deployed model never sees what it was trained on. Every
    caller gets it or none does.

    Leading silence is not a harmless detail. A classifier trained on leading-silence
    duration ALONE scores 15.1% EER on ASVspoof (arXiv:2106.12914), and the same paper
    reports signal models moving from 3.6% to 15.5% EER once silence is trimmed away --
    the crutch removed, not the model broken. Expect the trimmed run to look worse and
    be more honest.
    """
    import librosa
    if y.size == 0:
        return y
    yt, _ = librosa.effects.trim(y, top_db=top_db, frame_length=512, hop_length=128)
    # never hand back near-nothing; a clip that is silent by this threshold stays whole
    return np.ascontiguousarray(yt) if yt.size > sr // 10 else y


def prepare(path, nb_samp: int, target_sr: int = TARGET_SR, normalise: bool = True,
            trim: bool = False):
    """File -> one fixed-length window, ready for RawNet."""
    y = load_audio(path, target_sr, normalise)
    if trim:
        y = trim_silence(y, target_sr)
    return pad(y, nb_samp)
