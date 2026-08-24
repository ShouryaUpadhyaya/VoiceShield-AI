"""Shared audio front-end for VoiceShield.

This module is imported by BOTH the training pipeline and the FastAPI
predictor. That is deliberate: divergence between the training front-end and
the serving front-end is the single most common cause of a model that scores
well offline and fails in the demo. If you change a step here, it changes in
both places at once.

Pipeline order (fixed):
    decode -> mono -> resample 16 kHz -> DC removal -> silence policy
    -> RMS normalise -> fixed-length crop/pad

Augmentation is NOT part of this module; it belongs to training only and lives
in ml/deepfake_detection/preprocessing/augment.py.
"""

from __future__ import annotations

import io
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import soundfile as sf
import soxr

from ml.common.constants import (
    DEFAULT_SILENCE_POLICY,
    MIN_RMS_DBFS,
    SAMPLE_RATE,
    SEGMENT_SAMPLES,
    SILENCE_POLICIES,
    SILENCE_TOP_DB,
    SOUNDFILE_SUFFIXES,
    TARGET_DBFS,
)

CropMode = Literal["random", "center", "start"]


class AudioDecodeError(ValueError):
    """Raised when an upload cannot be decoded into usable audio."""


@dataclass(frozen=True)
class FrontEndConfig:
    """Every knob the front-end has. Persisted next to the model checkpoint so
    inference can reconstruct the exact training front-end."""

    sample_rate: int = SAMPLE_RATE
    segment_samples: int = SEGMENT_SAMPLES
    silence_policy: str = DEFAULT_SILENCE_POLICY
    silence_top_db: float = SILENCE_TOP_DB
    target_dbfs: float = TARGET_DBFS
    normalize: bool = True

    def __post_init__(self) -> None:
        if self.silence_policy not in SILENCE_POLICIES:
            raise ValueError(
                f"silence_policy must be one of {SILENCE_POLICIES}, got {self.silence_policy!r}"
            )


# --------------------------------------------------------------------------
# Decoding
# --------------------------------------------------------------------------

def _decode_soundfile(source: str | Path | bytes) -> tuple[np.ndarray, int]:
    handle = io.BytesIO(source) if isinstance(source, bytes) else str(source)
    audio, sr = sf.read(handle, dtype="float32", always_2d=True)
    return audio, sr


def _decode_ffmpeg(source: str | Path | bytes, sample_rate: int) -> tuple[np.ndarray, int]:
    """Fallback decoder for containers libsndfile cannot open (mp3/m4a/webm).

    ffmpeg does the resample here as well; going straight to the target rate in
    the decoder is both faster and avoids a redundant resample pass.
    """
    if shutil.which("ffmpeg") is None:
        raise AudioDecodeError("ffmpeg is required to decode this format but is not installed")

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
        "-i", "pipe:0" if isinstance(source, bytes) else str(source),
        "-map", "0:a:0",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-f", "f32le",
        "pipe:1",
    ]
    proc = subprocess.run(
        cmd,
        input=source if isinstance(source, bytes) else None,
        capture_output=True,
        timeout=60,
    )
    if proc.returncode != 0 or not proc.stdout:
        detail = proc.stderr.decode("utf-8", "replace").strip()[:300]
        raise AudioDecodeError(f"ffmpeg could not decode the audio: {detail}")

    audio = np.frombuffer(proc.stdout, dtype="<f4").astype(np.float32, copy=True)
    return audio.reshape(-1, 1), sample_rate


def decode(source: str | Path | bytes, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Decode any supported input to mono float32 at `sample_rate`.

    `source` may be a filesystem path (training) or raw bytes (an API upload).
    """
    suffix = Path(str(source)).suffix.lower() if not isinstance(source, bytes) else ""

    if isinstance(source, bytes) or suffix in SOUNDFILE_SUFFIXES:
        try:
            audio, sr = _decode_soundfile(source)
        except Exception:
            audio, sr = _decode_ffmpeg(source, sample_rate)
    else:
        audio, sr = _decode_ffmpeg(source, sample_rate)

    if audio.size == 0:
        raise AudioDecodeError("decoded audio is empty")

    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    mono = np.ascontiguousarray(mono, dtype=np.float32)

    if sr != sample_rate:
        mono = resample(mono, sr, sample_rate)
    return mono


def resample(audio: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return audio
    # soxr VHQ: the resampler's own artefacts must sit well below the synthesis
    # artefacts we are trying to detect.
    return soxr.resample(audio, sr_in, sr_out, quality="VHQ").astype(np.float32, copy=False)


# --------------------------------------------------------------------------
# Conditioning
# --------------------------------------------------------------------------

def remove_dc(audio: np.ndarray) -> np.ndarray:
    return (audio - float(np.mean(audio))).astype(np.float32, copy=False)


def dbfs(audio: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)) + 1e-12))
    return 20.0 * float(np.log10(max(rms, 1e-12)))


def rms_normalize(audio: np.ndarray, target_dbfs: float = TARGET_DBFS) -> np.ndarray:
    """Level-normalise so loudness can never act as a class cue.

    Guarded against clipping: if the required gain would push the peak past
    full scale we back it off, because clipping would itself be an artefact.
    """
    current = dbfs(audio)
    if current <= MIN_RMS_DBFS:
        return audio  # effectively silence; amplifying it only amplifies noise

    gain = 10.0 ** ((target_dbfs - current) / 20.0)
    peak = float(np.max(np.abs(audio))) or 1e-12
    gain = min(gain, 0.99 / peak)
    return (audio * gain).astype(np.float32, copy=False)


def trim_edges(audio: np.ndarray, top_db: float = SILENCE_TOP_DB) -> np.ndarray:
    """Strip leading/trailing silence using a frame-energy threshold.

    Deliberately not librosa.effects.trim: we want zero heavyweight imports on
    the serving path, and the logic is four lines.
    """
    frame, hop = 512, 128
    if audio.size < frame:
        return audio

    n_frames = 1 + (audio.size - frame) // hop
    frames = np.lib.stride_tricks.as_strided(
        audio, shape=(n_frames, frame), strides=(audio.strides[0] * hop, audio.strides[0])
    )
    energy = np.sqrt(np.mean(np.square(frames, dtype=np.float64), axis=1) + 1e-12)
    peak = float(energy.max())
    if peak <= 0:
        return audio

    voiced = np.flatnonzero(20.0 * np.log10(energy / peak) > -top_db)
    if voiced.size == 0:
        return audio

    start = int(voiced[0]) * hop
    end = min(audio.size, (int(voiced[-1]) + 1) * hop + frame)
    return audio[start:end]


def apply_silence_policy(audio: np.ndarray, policy: str, top_db: float) -> np.ndarray:
    if policy == "keep":
        return audio
    if policy == "trim_edges":
        return trim_edges(audio, top_db)
    raise ValueError(f"unknown silence policy {policy!r}")


# --------------------------------------------------------------------------
# Length handling
# --------------------------------------------------------------------------

def pad_or_crop(
    audio: np.ndarray,
    length: int = SEGMENT_SAMPLES,
    mode: CropMode = "center",
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Force the clip to exactly `length` samples.

    Short clips are tiled rather than zero-padded: a block of digital silence is
    itself a strong artefact, and padding one class more often than the other
    would hand the model a shortcut.
    """
    if audio.size == 0:
        raise AudioDecodeError("cannot pad empty audio")

    if audio.size < length:
        reps = int(np.ceil(length / audio.size))
        audio = np.tile(audio, reps)

    if audio.size == length:
        return audio

    if mode == "random":
        rng = rng or np.random.default_rng()
        offset = int(rng.integers(0, audio.size - length + 1))
    elif mode == "center":
        offset = (audio.size - length) // 2
    else:
        offset = 0
    return audio[offset : offset + length]


def sliding_windows(
    audio: np.ndarray, length: int = SEGMENT_SAMPLES, hop: int | None = None
) -> np.ndarray:
    """Split a long clip into overlapping fixed-length windows.

    Evaluating every window and pooling the scores beats scoring one arbitrary
    4 s crop of a 30 s call, and it is what the streaming path will reuse.
    """
    hop = hop or length // 2
    if audio.size <= length:
        return pad_or_crop(audio, length, mode="center")[None, :]

    starts = list(range(0, audio.size - length + 1, hop))
    if starts[-1] + length < audio.size:
        starts.append(audio.size - length)
    return np.stack([audio[s : s + length] for s in starts])


# --------------------------------------------------------------------------
# The one entry point
# --------------------------------------------------------------------------

def preprocess(
    source: str | Path | bytes | np.ndarray,
    config: FrontEndConfig | None = None,
    crop: CropMode = "center",
    rng: np.random.Generator | None = None,
    fixed_length: bool = True,
) -> np.ndarray:
    """Decode and condition audio into model-ready float32.

    Training calls this with crop="random"; inference calls it with
    crop="center" (or with fixed_length=False, then windows the result).
    """
    cfg = config or FrontEndConfig()

    audio = (
        np.ascontiguousarray(source, dtype=np.float32)
        if isinstance(source, np.ndarray)
        else decode(source, cfg.sample_rate)
    )

    audio = remove_dc(audio)
    audio = apply_silence_policy(audio, cfg.silence_policy, cfg.silence_top_db)
    if cfg.normalize:
        audio = rms_normalize(audio, cfg.target_dbfs)

    if fixed_length:
        audio = pad_or_crop(audio, cfg.segment_samples, mode=crop, rng=rng)
    return audio
