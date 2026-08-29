"""
Integration script to simulate a real-time call from the Media Gateway to the ML Server.

This script acts like a mock Media Gateway to directly test the ML WebSocket server.
It generates a synthetic 16kHz sine wave, resamples it to 48kHz (like Android would),
encodes it as PCM16 bytes, and pushes chunks to the ML server over WebSockets.

Requirements:
    pip install websockets numpy soxr
"""

import asyncio
import json
import uuid
import time
import numpy as np
import websockets
import soxr


async def simulate_call():
    uri = "ws://localhost:8011/"
    session_id = str(uuid.uuid4())
    print(f"Starting simulated call {session_id} to {uri}")

    try:
        async with websockets.connect(uri) as ws:
            print("Connected to ML Server.")

            for seq in range(1, 4):  # Send 3 chunks (9 seconds of audio)
                print(f"\n--- Sending chunk {seq} ---")
                
                # 1. Generate synthetic audio (3 seconds of 440 Hz sine wave)
                t = np.linspace(0, 3.0, int(16000 * 3.0), endpoint=False, dtype=np.float32)
                audio_16k = 0.5 * np.sin(2 * np.pi * 440.0 * t)
                
                # 2. Resample to 48kHz (Gateway format)
                audio_48k = soxr.resample(audio_16k, 16000, 48000, quality="HQ")
                
                # 3. Convert to PCM16 LE bytes
                audio_i16 = (audio_48k * 32767).astype("<i2")
                pcm_bytes = audio_i16.tobytes()

                # 4. Create Gateway metadata
                meta = {
                    "type": "audio.chunk",
                    "session_id": session_id,
                    "sequence": seq,
                    "timestamp_ms": (seq - 1) * 3000,
                    "duration_ms": 3000,
                    "sample_rate": 48000,
                    "channels": 1,
                    "encoding": "pcm_s16le",
                    "bytes": len(pcm_bytes)
                }

                # 5. Send Text Frame (JSON)
                await ws.send(json.dumps(meta))
                
                # 6. Send Binary Frame (PCM bytes)
                await ws.send(pcm_bytes)
                print(f"Sent {len(pcm_bytes)} bytes of PCM audio.")

                # 7. Wait for Score Response
                response = await ws.recv()
                print("Received Score from ML:")
                print(json.dumps(json.loads(response), indent=2))
                
                # Wait 1 second before next chunk
                await asyncio.sleep(1)
                
            print("\nCall completed successfully!")
            
    except ConnectionRefusedError:
        print("ERROR: Could not connect. Is the ML Server running on port 8011?")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(simulate_call())
