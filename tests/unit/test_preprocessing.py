"""Contract tests for the shared audio front-end.

These guard the property that matters most: training and serving must condition
audio identically. Every assertion here corresponds to a way that guarantee
could silently break.
"""

from __future__ import annotations

import subprocess

import numpy as np
import pytest
import soundfile as sf

from ml.common.audio_utils import (
    AudioDecodeError,
    FrontEndConfig,
    dbfs,
    decode,
    pad_or_crop,
    preprocess,
    remove_dc,
    rms_normalize,
    sliding_windows,
    trim_edges,
)
from ml.common.constants import SAMPLE_RATE, SEGMENT_SAMPLES


@pytest.fixture
def speech() -> np.ndarray:
    t = np.arange(SAMPLE_RATE * 3) / SAMPLE_RATE
    return (0.3 * np.sin(2 * np.pi * 180 * t) * (1 + 0.4 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)


@pytest.fixture
def wav_file(tmp_path, speech):
    padded = np.concatenate([np.zeros(SAMPLE_RATE // 2, np.float32), speech, np.zeros(SAMPLE_RATE, np.float32)])
    path = tmp_path / "clip.wav"
    sf.write(path, padded, SAMPLE_RATE)
    return path


def test_output_is_exact_contract(wav_file):
    out = preprocess(wav_file)
    assert out.shape == (SEGMENT_SAMPLES,)
    assert out.dtype == np.float32
    assert np.isfinite(out).all()
    assert np.abs(out).max() <= 1.0


def test_formats_converge(tmp_path, wav_file):
    """wav / mp3 / m4a must all land on the same shape and level — otherwise the
    model sees a different distribution depending on what the caller uploaded."""
    mp3, m4a = tmp_path / "clip.mp3", tmp_path / "clip.m4a"
    for target, args in ((mp3, ["-ar", "44100", "-b:a", "96k"]), (m4a, ["-ar", "48000", "-c:a", "aac"])):
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav_file), *args, str(target)],
            check=True,
        )

    outs = [preprocess(p) for p in (wav_file, mp3, m4a)]
    assert {o.shape for o in outs} == {(SEGMENT_SAMPLES,)}
    levels = [dbfs(o) for o in outs]
    assert max(levels) - min(levels) < 0.5


def test_bytes_and_path_agree(wav_file):
    """The API receives bytes; training receives paths. Same audio, same result."""
    from_path = preprocess(wav_file)
    from_bytes = preprocess(wav_file.read_bytes())
    assert np.allclose(from_path, from_bytes, atol=1e-6)


def test_resampling_happens(tmp_path, speech):
    path = tmp_path / "highrate.wav"
    sf.write(path, np.tile(speech, 2), 44100)
    assert decode(path).size == pytest.approx(2 * speech.size * SAMPLE_RATE / 44100, rel=0.01)


def test_level_normalisation_removes_gain_as_a_cue(wav_file):
    """Two copies of the same clip at wildly different gains must normalise to
    the same level, or loudness becomes a shortcut feature."""
    quiet = preprocess(sf.read(wav_file, dtype="float32")[0] * 0.01)
    loud = preprocess(sf.read(wav_file, dtype="float32")[0] * 0.9)
    assert abs(dbfs(quiet) - dbfs(loud)) < 0.5


def test_normalisation_never_clips():
    audio = np.full(SAMPLE_RATE, 0.99, dtype=np.float32)
    assert np.abs(rms_normalize(audio)).max() <= 1.0


def test_silence_of_pure_digital_zero_is_left_alone():
    """Amplifying silence to the target level would turn dither into 'speech'."""
    silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
    assert np.array_equal(rms_normalize(silence), silence)


def test_trim_edges_removes_only_the_edges(speech):
    padded = np.concatenate([np.zeros(SAMPLE_RATE, np.float32), speech, np.zeros(SAMPLE_RATE, np.float32)])
    trimmed = trim_edges(padded)
    assert trimmed.size < padded.size
    assert trimmed.size >= speech.size * 0.9


def test_silence_policies_differ(wav_file):
    kept = preprocess(wav_file, FrontEndConfig(silence_policy="keep"), fixed_length=False)
    trimmed = preprocess(wav_file, FrontEndConfig(silence_policy="trim_edges"), fixed_length=False)
    assert trimmed.size < kept.size


def test_unknown_silence_policy_rejected():
    with pytest.raises(ValueError):
        FrontEndConfig(silence_policy="whatever")


def test_short_clips_are_tiled_not_zero_padded():
    """Zero-padding would add a block of digital silence — itself an artefact
    the model could learn instead of detecting synthesis."""
    short = np.sin(np.arange(SAMPLE_RATE // 2) * 0.05).astype(np.float32)
    out = pad_or_crop(short, SEGMENT_SAMPLES)
    assert out.shape == (SEGMENT_SAMPLES,)
    assert (out != 0).mean() > 0.99


def test_crop_modes(speech):
    long_audio = np.tile(speech, 4)
    rng = np.random.default_rng(0)
    assert pad_or_crop(long_audio, SEGMENT_SAMPLES, "center").shape == (SEGMENT_SAMPLES,)
    assert pad_or_crop(long_audio, SEGMENT_SAMPLES, "start").shape == (SEGMENT_SAMPLES,)
    crops = {pad_or_crop(long_audio, SEGMENT_SAMPLES, "random", rng).tobytes() for _ in range(8)}
    assert len(crops) > 1, "random crop must actually vary between epochs"


def test_dc_offset_removed():
    biased = np.full(SAMPLE_RATE, 0.5, dtype=np.float32) + np.sin(np.arange(SAMPLE_RATE) * 0.01).astype(np.float32)
    assert abs(float(np.mean(remove_dc(biased)))) < 1e-6


def test_sliding_windows_cover_the_whole_clip(speech):
    long_audio = np.tile(speech, 5)  # 15 s
    windows = sliding_windows(long_audio, SEGMENT_SAMPLES)
    assert windows.shape[1] == SEGMENT_SAMPLES
    assert windows.shape[0] > 1
    assert np.allclose(windows[-1], long_audio[-SEGMENT_SAMPLES:])


def test_empty_and_garbage_inputs_raise():
    with pytest.raises(AudioDecodeError):
        preprocess(b"this is not audio at all")
    with pytest.raises(AudioDecodeError):
        pad_or_crop(np.array([], dtype=np.float32))


def test_preprocess_is_deterministic(wav_file):
    assert np.array_equal(preprocess(wav_file), preprocess(wav_file))
