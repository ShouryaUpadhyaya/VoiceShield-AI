"""
Android Client Simulator

Simulates an Android client connecting to the Media Gateway (Node.js) on port 8010.
This allows end-to-end testing of the complete pipeline (Android -> Gateway -> ML Server -> Database -> Frontend)
without needing a physical Android device.

Usage:
  python tests/integration/test_android_simulator.py [path_to_audio_file_or_directory]

If you provide a directory, it will loop through all .wav and .flac files and stream them.
If you provide no arguments, it uses a built-in librosa sample.
"""

import asyncio
import json
import uuid
import sys
import os
import glob
import numpy as np
import websockets
import soundfile as sf
import soxr
import librosa

GATEWAY_URI = "ws://localhost:8010"

async def stream_audio_file(file_path: str):
    session_id = str(uuid.uuid4())
    print(f"\n[{session_id}] Starting call from file: {os.path.basename(file_path)}")

    # 1. Load audio
    audio, sr = librosa.load(file_path, sr=None, mono=True)

    print(f"[{session_id}] Loaded audio: {len(audio)/sr:.2f} seconds at {sr}Hz")

    # 2. Resample to 48kHz (Gateway format)
    if sr != 48000:
        audio_48k = soxr.resample(audio, sr, 48000, quality="HQ")
    else:
        audio_48k = audio

    # Android sends audio in chunks, let's say every 100ms
    # 48000 samples/sec * 0.1 sec = 4800 samples per chunk
    chunk_samples = int(48000 * 0.1)

    try:
        async with websockets.connect(GATEWAY_URI) as ws:
            print(f"[{session_id}] Connected to Media Gateway.")

            # 3. Send session.start
            start_msg = {
                "type": "session.start",
                "session_id": session_id,
                "source": f"synthetic_{os.path.basename(file_path)}",
                "sample_rate": 48000,
                "channels": 1,
                "encoding": "pcm_s16le"
            }
            await ws.send(json.dumps(start_msg))
            print(f"[{session_id}] Sent session.start")

            # Wait briefly to let Gateway initialize session
            await asyncio.sleep(0.1)

            # 4. Stream binary PCM audio
            print(f"[{session_id}] Streaming audio frames...")
            total_sent = 0
            
            for start in range(0, len(audio_48k), chunk_samples):
                end = min(start + chunk_samples, len(audio_48k))
                chunk = audio_48k[start:end]

                # Convert to PCM16 LE
                chunk_i16 = (chunk * 32767).astype("<i2")
                pcm_bytes = chunk_i16.tobytes()

                await ws.send(pcm_bytes)
                total_sent += len(pcm_bytes)

                # Simulate real-time streaming delay (send 100ms of audio, wait ~100ms)
                # But we can speed it up a little bit if we want faster tests. Let's do 50% realtime.
                await asyncio.sleep(0.05)

            print(f"[{session_id}] Finished streaming {total_sent} bytes.")

            # 5. Send session.stop
            stop_msg = {
                "type": "session.stop",
                "session_id": session_id
            }
            await ws.send(json.dumps(stop_msg))
            print(f"[{session_id}] Sent session.stop")

            # Wait briefly to allow Gateway to process final chunks
            await asyncio.sleep(3.0)

    except ConnectionRefusedError:
        print(f"[{session_id}] ERROR: Could not connect to {GATEWAY_URI}. Is Media Gateway running?")
    except Exception as e:
        print(f"[{session_id}] An error occurred: {e}")

async def run_tests(path: str):
    if os.path.isdir(path):
        # Find all audio files recursively using Path
        from pathlib import Path
        p = Path(path)
        files = list(p.rglob("*.wav")) + list(p.rglob("*.flac")) + list(p.rglob("*.aac"))
        files = [str(f) for f in files]
        if not files:
            print(f"No audio files found in directory {path}")
            return
            
        print(f"Found {len(files)} audio files in dataset. Testing sequentially...")
        for f in files:
            await stream_audio_file(f)
            # Wait between calls
            await asyncio.sleep(2.0)
    else:
        if not os.path.exists(path):
            print(f"File {path} not found.")
            return
        await stream_audio_file(path)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_path = sys.argv[1]
    else:
        # Default to a librosa sample
        target_path = librosa.example('trumpet')
        
    asyncio.run(run_tests(target_path))
