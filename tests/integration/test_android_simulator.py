"""
Android Client Simulator

Simulates an Android client connecting to the Media Gateway (Node.js) on port 8010.
This allows end-to-end testing of the complete pipeline (Android -> Gateway -> ML Server -> Database -> Frontend)
without needing a physical Android device.

Usage:
  python tests/integration/test_android_simulator.py [path_to_audio_file_or_directory] [--concurrency 1] [--speed 1.0]

- If you provide a directory, it will loop through all .wav and .flac files and stream them.
- If you provide no arguments, it uses a built-in librosa sample.
- Use Ctrl+C during a stream to skip to the next file(s).
"""

import asyncio
import json
import uuid
import sys
import os
import argparse
from pathlib import Path
import numpy as np
import websockets
import soundfile as sf
import soxr
import librosa

GATEWAY_URI = "ws://localhost:8010"

async def stream_audio_file(file_path: str, speed: float = 1.0):
    session_id = str(uuid.uuid4())
    print(f"\n[{session_id}] Starting call from file: {os.path.basename(file_path)}")

    # 1. Load audio
    try:
        audio, sr = librosa.load(file_path, sr=None, mono=True)
    except Exception as e:
        print(f"[{session_id}] Failed to load audio: {e}")
        return

    print(f"[{session_id}] Loaded audio: {len(audio)/sr:.2f} seconds at {sr}Hz")

    # 2. Resample to 48kHz (Gateway format)
    if sr != 48000:
        audio_48k = soxr.resample(audio, sr, 48000, quality="HQ")
    else:
        audio_48k = audio

    # Android sends audio in chunks, let's say every 100ms
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
            
            await asyncio.sleep(0.1)

            # 4. Stream binary PCM audio
            print(f"[{session_id}] Streaming audio frames (Speed: {speed}x)...")
            total_sent = 0
            
            for start in range(0, len(audio_48k), chunk_samples):
                end = min(start + chunk_samples, len(audio_48k))
                chunk = audio_48k[start:end]

                chunk_i16 = (chunk * 32767).astype("<i2")
                pcm_bytes = chunk_i16.tobytes()

                await ws.send(pcm_bytes)
                total_sent += len(pcm_bytes)

                # Simulate streaming delay scaled by speed (0 means instant)
                if speed > 0:
                    await asyncio.sleep(0.1 / speed)
                else:
                    await asyncio.sleep(0) # Yield control

            print(f"[{session_id}] Finished streaming {total_sent} bytes.")

            # 5. Send session.stop
            stop_msg = {
                "type": "session.stop",
                "session_id": session_id
            }
            await ws.send(json.dumps(stop_msg))
            
            # Wait briefly to allow Gateway to process final chunks
            if speed > 0:
                await asyncio.sleep(2.0 / speed)

    except asyncio.CancelledError:
        print(f"\n[{session_id}] Stream skipped/cancelled.")
        raise
    except ConnectionRefusedError:
        print(f"[{session_id}] ERROR: Could not connect to {GATEWAY_URI}. Is Media Gateway running?")
    except Exception as e:
        print(f"[{session_id}] An error occurred: {e}")

async def run_tests(path: str, concurrency: int, speed: float):
    files = []
    if os.path.isdir(path):
        p = Path(path)
        files = list(p.rglob("*.wav")) + list(p.rglob("*.flac")) + list(p.rglob("*.aac")) + list(p.rglob("*.mp3"))
        files = [str(f) for f in files]
        if not files:
            print(f"No audio files found in directory {path}")
            return
        print(f"Found {len(files)} audio files in dataset.")
    else:
        if not os.path.exists(path):
            print(f"File {path} not found.")
            return
        files = [path]

    print(f"Testing with concurrency={concurrency} and speed={speed}x. Press Ctrl+C to skip current batch.")
    
    # Process in batches based on concurrency
    for i in range(0, len(files), concurrency):
        batch = files[i:i+concurrency]
        tasks = [asyncio.create_task(stream_audio_file(f, speed)) for f in batch]
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            print("\n[Simulator] Ctrl+C detected. Skipping current batch of files...")
            for t in tasks:
                t.cancel()
            await asyncio.sleep(0.5) # Allow cleanup
            continue
            
        if speed > 0:
            await asyncio.sleep(1.0 / speed)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Android Client Simulator")
    parser.add_argument("path", nargs="?", default="", help="Path to audio file or directory")
    parser.add_argument("-c", "--concurrency", type=int, default=1, help="Number of concurrent calls to simulate")
    parser.add_argument("-s", "--speed", type=float, default=2.0, help="Streaming speed multiplier (0 for instant/no delay)")
    
    args = parser.parse_args()
    
    target_path = args.path
    if not target_path:
        target_path = librosa.example('trumpet')
        
    try:
        asyncio.run(run_tests(target_path, args.concurrency, args.speed))
    except KeyboardInterrupt:
        print("\n[Simulator] Exiting...")
