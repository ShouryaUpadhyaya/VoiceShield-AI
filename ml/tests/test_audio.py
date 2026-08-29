"""
Tests for the ML pipeline audio conversion (PCM16 -> float32 @ 16kHz).
"""
import numpy as np
import pytest

from ml.pipeline.audio import decode_gateway_chunk, AudioDecodeError
from ml.common.constants import GATEWAY_CHUNK_BYTES, WINDOW_SAMPLES


def test_decode_gateway_chunk_success():
    """Valid 3-second PCM16 chunk should yield exactly WINDOW_SAMPLES float32s."""
    # Create 3 seconds of dummy audio at 48kHz (288,000 bytes)
    dummy_i16 = np.ones(GATEWAY_CHUNK_BYTES // 2, dtype="<i2")
    pcm_bytes = dummy_i16.tobytes()

    assert len(pcm_bytes) == GATEWAY_CHUNK_BYTES

    # Decode
    audio_16k = decode_gateway_chunk(pcm_bytes, src_sr=48000, dst_sr=16000, strict_length=True)

    # 3 sec @ 16kHz = 48,000 samples
    assert len(audio_16k) == WINDOW_SAMPLES
    assert audio_16k.dtype == np.float32

    # Since input is constant 1s, output should be close to 1/32768
    assert np.all(audio_16k > 0)


def test_decode_gateway_chunk_padding():
    """A chunk shorter than 3 seconds should be zero-padded to WINDOW_SAMPLES."""
    # Create 1 second of dummy audio at 48kHz (96,000 bytes)
    dummy_i16 = np.ones(48000, dtype="<i2")
    pcm_bytes = dummy_i16.tobytes()

    # Decode (strict_length=False)
    audio_16k = decode_gateway_chunk(pcm_bytes, src_sr=48000, dst_sr=16000, strict_length=False)

    # Output should still be exactly 3 seconds long
    assert len(audio_16k) == WINDOW_SAMPLES

    # First third should be non-zero (approx)
    assert np.any(audio_16k[:16000] > 0)

    # The rest should be exactly zero (padding)
    assert np.all(audio_16k[16500:] == 0.0)


def test_decode_gateway_chunk_odd_bytes():
    """Odd byte counts cannot be PCM16 and should raise AudioDecodeError."""
    bad_bytes = b"\x00" * 15  # 15 bytes
    with pytest.raises(AudioDecodeError, match="odd byte count"):
        decode_gateway_chunk(bad_bytes)


def test_decode_gateway_chunk_empty():
    """Empty payload should raise AudioDecodeError."""
    with pytest.raises(AudioDecodeError, match="Empty PCM payload"):
        decode_gateway_chunk(b"")
