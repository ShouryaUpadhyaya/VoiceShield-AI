"""Training-time augmentation for spoof detection.

Two families, and the second one is the reason this project works on real calls:

1. RawBoost (Tak et al., ICASSP 2022) — the ASVspoof 2021 standard. Convolutive
   and impulsive noise applied directly to the waveform, no external corpora
   needed. Stops the model latching onto channel colouration.

2. Telephony codec simulation — the target deployment is a *phone call*, so
   training audio must pass through the same 8 kHz narrowband codecs the
   production audio does. A detector trained on clean 16 kHz studio audio reads
   near-chance on G.711 telephony, because the artefacts it keys on live above
   4 kHz where the codec has already thrown them away.

Augmentation is applied ONLY at training time and ONLY to the training split.
Dev/eval stay clean, except in the deliberate robustness evaluation, which
applies these same transforms as a controlled test condition.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field

import numpy as np

from ml.common.constants import SAMPLE_RATE

# --------------------------------------------------------------------------
# RawBoost
# --------------------------------------------------------------------------

def _rand_fir(rng: np.random.Generator, n_taps: int, min_coeff_db: float, max_coeff_db: float) -> np.ndarray:
    """Random linear FIR filter with log-spaced coefficient magnitudes."""
    half = n_taps // 2
    b = np.zeros(n_taps, dtype=np.float64)
    b[half] = 1.0
    mags = 10 ** (rng.uniform(min_coeff_db, max_coeff_db, size=n_taps) / 20.0)
    signs = rng.choice([-1.0, 1.0], size=n_taps)
    b = b + mags * signs / n_taps
    return b / (np.abs(b).sum() + 1e-12)


def linear_convolutive_noise(
    audio: np.ndarray,
    rng: np.random.Generator,
    n_filters: int = 5,
    n_taps: int = 21,
    min_coeff_db: float = -5.0,
    max_coeff_db: float = 20.0,
) -> np.ndarray:
    """RawBoost algo 1: cascade of random FIR filters (channel/device variation)."""
    out = audio.astype(np.float64, copy=True)
    for _ in range(int(rng.integers(1, n_filters + 1))):
        b = _rand_fir(rng, n_taps, min_coeff_db, max_coeff_db)
        out = np.convolve(out, b, mode="same")
    return out.astype(np.float32)


def impulsive_noise(
    audio: np.ndarray, rng: np.random.Generator, snr_db_range: tuple[float, float] = (5.0, 20.0)
) -> np.ndarray:
    """RawBoost algo 2: sparse signal-dependent impulses (transmission glitches)."""
    out = audio.astype(np.float64, copy=True)
    n_imp = int(rng.uniform(0.0001, 0.01) * out.size)
    if n_imp == 0:
        return out.astype(np.float32)

    idx = rng.integers(0, out.size, size=n_imp)
    snr = rng.uniform(*snr_db_range)
    scale = np.sqrt(np.mean(out**2) / (10 ** (snr / 10.0)) + 1e-12)
    out[idx] += scale * rng.standard_normal(n_imp)
    return out.astype(np.float32)


def coloured_additive_noise(
    audio: np.ndarray, rng: np.random.Generator, snr_db_range: tuple[float, float] = (10.0, 40.0)
) -> np.ndarray:
    """RawBoost algo 3: stationary coloured noise at a controlled SNR."""
    noise = rng.standard_normal(audio.size)
    b = _rand_fir(rng, 21, -5.0, 20.0)
    noise = np.convolve(noise, b, mode="same")

    snr = rng.uniform(*snr_db_range)
    sig_p = float(np.mean(audio.astype(np.float64) ** 2)) + 1e-12
    noise_p = float(np.mean(noise**2)) + 1e-12
    gain = np.sqrt(sig_p / (noise_p * 10 ** (snr / 10.0)))
    return (audio + gain * noise).astype(np.float32)


def rawboost(audio: np.ndarray, rng: np.random.Generator, algo: int = 4) -> np.ndarray:
    """algo 4 = series(1,2,3), the configuration that generalised best in the paper."""
    if algo == 1:
        return linear_convolutive_noise(audio, rng)
    if algo == 2:
        return impulsive_noise(audio, rng)
    if algo == 3:
        return coloured_additive_noise(audio, rng)
    if algo == 4:
        return coloured_additive_noise(impulsive_noise(linear_convolutive_noise(audio, rng), rng), rng)
    raise ValueError(f"unknown rawboost algo {algo}")


# --------------------------------------------------------------------------
# Codec simulation
# --------------------------------------------------------------------------

# Each entry is the ffmpeg encode leg; we always round-trip back to 16 kHz f32
# so the tensor shape the model sees never changes.
CODECS: dict[str, list[str]] = {
    "g711_ulaw": ["-ar", "8000", "-acodec", "pcm_mulaw", "-f", "wav"],
    "g711_alaw": ["-ar", "8000", "-acodec", "pcm_alaw", "-f", "wav"],
    "gsm": ["-ar", "8000", "-acodec", "gsm", "-f", "gsm"],
    "amr_nb": ["-ar", "8000", "-acodec", "libopencore_amrnb", "-b:a", "12.2k", "-f", "amr"],
    "opus_16k": ["-acodec", "libopus", "-b:a", "16k", "-f", "ogg"],
    "opus_32k": ["-acodec", "libopus", "-b:a", "32k", "-f", "ogg"],
    "mp3_64k": ["-acodec", "libmp3lame", "-b:a", "64k", "-f", "mp3"],
}


def _ffmpeg_roundtrip(audio: np.ndarray, encode_args: list[str], sample_rate: int) -> np.ndarray:
    raw = audio.astype("<f4").tobytes()

    enc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
         "-f", "f32le", "-ar", str(sample_rate), "-ac", "1", "-i", "pipe:0",
         *encode_args, "pipe:1"],
        input=raw, capture_output=True, timeout=30,
    )
    if enc.returncode != 0 or not enc.stdout:
        return audio

    dec = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
         "-i", "pipe:0", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "pipe:1"],
        input=enc.stdout, capture_output=True, timeout=30,
    )
    if dec.returncode != 0 or not dec.stdout:
        return audio

    out = np.frombuffer(dec.stdout, dtype="<f4").astype(np.float32, copy=True)
    return out if out.size else audio


def match_length(audio: np.ndarray, length: int) -> np.ndarray:
    """Codecs pad to their frame size, so a round-trip returns a slightly
    different sample count. Restore the original length or the batch will not
    collate."""
    if audio.size == length:
        return audio
    if audio.size > length:
        return audio[:length]
    return np.pad(audio, (0, length - audio.size), mode="wrap")


def apply_codec(audio: np.ndarray, codec: str, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Round-trip through a codec. Returns the input unchanged if that codec is
    unavailable in this ffmpeg build, so training never dies on a missing encoder.

    Costs ~650 ms per call (two ffmpeg spawns), which is why the online
    Augmenter defaults to codec_prob=0.0 and codec variants are baked into the
    cache offline instead — see ml/data/build_cache.py --codec-variants.
    """
    if codec not in CODECS:
        raise ValueError(f"unknown codec {codec!r}; known: {sorted(CODECS)}")
    return match_length(_ffmpeg_roundtrip(audio, CODECS[codec], sample_rate), audio.size)


def available_codecs() -> list[str]:
    """Probe once at startup so we only sample codecs this ffmpeg can actually do."""
    if shutil.which("ffmpeg") is None:
        return []
    probe = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, timeout=30)
    listing = probe.stdout.decode("utf-8", "replace")
    ok = []
    for name, args in CODECS.items():
        encoder = args[args.index("-acodec") + 1]
        if encoder in listing or encoder.startswith("pcm_"):
            ok.append(name)
    return ok


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

@dataclass
class AugmentConfig:
    """Probabilities are per-utterance and independent, so a clip can pick up
    both RawBoost and a codec — which is exactly what a cloned voice arriving
    over a real phone line looks like."""

    rawboost_prob: float = 0.5
    rawboost_algo: int = 4
    # 0.0 by default: a codec round-trip costs ~650 ms and would make the data
    # loader ~8x slower than the GPU step. Codec variants are precomputed into
    # the cache instead; the loader samples between clean and codec copies for
    # free. Raise this only for offline/robustness use.
    codec_prob: float = 0.0
    codecs: list[str] = field(default_factory=list)  # empty => probe at runtime
    gain_prob: float = 0.3
    gain_db_range: tuple[float, float] = (-6.0, 6.0)

    def resolve(self) -> "AugmentConfig":
        if not self.codecs:
            self.codecs = available_codecs()
        return self


class Augmenter:
    def __init__(self, config: AugmentConfig | None = None, seed: int | None = None):
        self.cfg = (config or AugmentConfig()).resolve()
        self.rng = np.random.default_rng(seed)

    def __call__(self, audio: np.ndarray) -> np.ndarray:
        out = audio

        if self.rng.random() < self.cfg.rawboost_prob:
            out = rawboost(out, self.rng, self.cfg.rawboost_algo)

        if self.cfg.codecs and self.rng.random() < self.cfg.codec_prob:
            out = apply_codec(out, str(self.rng.choice(self.cfg.codecs)))

        if self.rng.random() < self.cfg.gain_prob:
            out = out * 10 ** (self.rng.uniform(*self.cfg.gain_db_range) / 20.0)

        # Augmentation can push samples past full scale; scale back rather than
        # let a wrapped value masquerade as a synthesis artefact.
        peak = float(np.max(np.abs(out))) if out.size else 0.0
        if peak > 1.0:
            out = out / peak * 0.99

        return match_length(out, audio.size).astype(np.float32, copy=False)
