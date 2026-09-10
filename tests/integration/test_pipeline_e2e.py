import pytest
import asyncio
import os
import sys

# Ensure we can import from the root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from tests.integration.test_android_simulator import run_tests

@pytest.mark.asyncio
async def test_real_audio_pipeline():
    """Verify that the simulator runs successfully on real audio."""
    path = "data/wavs/real/better_call_Sure_ya/Audio_001.wav"
    if os.path.exists(path):
        # Run simulator at high speed
        await run_tests(path, concurrency=1, speed=100.0)

@pytest.mark.asyncio
async def test_fake_audio_pipeline():
    """Verify that the simulator runs successfully on fake audio."""
    path = "data/wavs/fake/easy/fake_sample_1.wav"
    if os.path.exists(path):
        # Run simulator at high speed
        await run_tests(path, concurrency=1, speed=100.0)
