"""
Audio decoding boundary: Gateway PCM16 → ML-ready float32 @ 16 kHz.

The gateway sends:
    48,000 Hz | mono | PCM16 LE | 3 sec → 288,000 bytes → 144,000 int16 samples

Every ML model in this pipeline expects:
    16,000 Hz | mono | float32 [-1, 1] | 3 sec → 48,000 samples

Conversion chain:
    bytes
      ↓  frombuffer(dtype=int16)
    144,000 int16 samples
      ↓  / 32768.0
    144,000 float32 samples  [-1, 1]
      ↓  soxr.resample(48000 → 16000)
    48,000 float32 samples   [-1, 1]

We use soxr for resampling because:
  - It is already in requirements.txt
  - It is numerically correct (HQ sinc filter)
  - It does NOT alter duration (3 s in → 3 s out)
  - Significantly faster than librosa.resample for this use-case
"""
from __future__ import annotations

import numpy as np
import soxr

from ml.common.constants import (
    GATEWAY_SAMPLE_RATE,
    SAMPLE_RATE,
    WINDOW_SAMPLES,
    GATEWAY_CHUNK_BYTES,
)


class AudioDecodeError(ValueError):
    """Raised when the raw PCM payload is malformed or out of range."""


def decode_gateway_chunk(
    pcm_bytes: bytes,
    *,
    src_sr: int = GATEWAY_SAMPLE_RATE,
    dst_sr: int = SAMPLE_RATE,
    strict_length: bool = False,
) -> np.ndarray:
    """
    Decode one raw PCM16 payload from the Media Gateway.

    Parameters
    ----------
    pcm_bytes:
        Raw bytes exactly as received from the gateway WebSocket binary frame.
    src_sr:
        Source sample rate (gateway default: 48,000 Hz).
    dst_sr:
        Target sample rate for ML models (default: 16,000 Hz).
    strict_length:
        If True, raise AudioDecodeError unless the byte count exactly matches
        GATEWAY_CHUNK_BYTES (288,000). If False, accept shorter chunks (e.g. a
        final partial chunk at call end) and zero-pad at the model stage.

    Returns
    -------
    np.ndarray
        Shape (48000,) — float32 mono samples at 16 kHz, values in [-1, 1].
        Returned samples will be exactly WINDOW_SAMPLES long (zero-padded if
        the input was shorter than a full 3-second chunk).
    """

    # ------------------------------------------------------------------ #
    # 1. Byte-level validation
    # ------------------------------------------------------------------ #

    if len(pcm_bytes) == 0:
        raise AudioDecodeError("Empty PCM payload received from gateway.")

    if len(pcm_bytes) % 2 != 0:
        raise AudioDecodeError(
            f"PCM payload has odd byte count ({len(pcm_bytes)}); "
            "cannot interpret as int16 samples."
        )

    if strict_length and len(pcm_bytes) != GATEWAY_CHUNK_BYTES:
        raise AudioDecodeError(
            f"Expected exactly {GATEWAY_CHUNK_BYTES} bytes "
            f"(3-second chunk @ {src_sr} Hz), got {len(pcm_bytes)}."
        )

    # ------------------------------------------------------------------ #
    # 2. bytes → int16 numpy array (little-endian)
    # ------------------------------------------------------------------ #

    samples_i16 = np.frombuffer(pcm_bytes, dtype="<i2")  # little-endian int16

    # ------------------------------------------------------------------ #
    # 3. int16 → float32 [-1, 1]
    # ------------------------------------------------------------------ #

    samples_f32 = samples_i16.astype(np.float32) / 32768.0

    # Clamp to [-1, 1] to handle any edge-case overflow
    samples_f32 = np.clip(samples_f32, -1.0, 1.0)

    # ------------------------------------------------------------------ #
    # 4. Resample src_sr → dst_sr using soxr (HQ sinc filter)
    # ------------------------------------------------------------------ #

    if src_sr != dst_sr:
        resampled = soxr.resample(samples_f32, src_sr, dst_sr, quality="HQ")
    else:
        resampled = samples_f32

    # ------------------------------------------------------------------ #
    # 5. Ensure exactly WINDOW_SAMPLES (48,000 for 3 s @ 16 kHz)
    # ------------------------------------------------------------------ #

    if len(resampled) > WINDOW_SAMPLES:
        resampled = resampled[:WINDOW_SAMPLES]
    elif len(resampled) < WINDOW_SAMPLES:
        pad_len = WINDOW_SAMPLES - len(resampled)
        resampled = np.pad(resampled, (0, pad_len), mode="constant")

    return resampled.astype(np.float32)


def compute_rms(audio: np.ndarray) -> float:
    """RMS energy of float32 audio for VAD / logging (NOT for normalization)."""
    if len(audio) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio)) + 1e-12))
