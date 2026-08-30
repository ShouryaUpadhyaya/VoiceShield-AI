import asyncio
import json
import logging
import random
import os
import time
from pathlib import Path
import websockets
import uuid

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

AUDIO_DIR = Path(__file__).parent / "test_audio"
WS_URL = "ws://127.0.0.1:8080/"
CHUNK_DURATION_MS = 3000
SAMPLE_RATE = 16000
BYTES_PER_MS = 32  # 16kHz * 2 bytes (16-bit) = 32000 bytes/sec -> 32 bytes/ms

async def stream_audio_file(filepath: Path):
    session_id = str(uuid.uuid4())
    logger.info(f"Starting simulated call: {filepath.name} (Session: {session_id})")

    try:
        async with websockets.connect(WS_URL) as ws:
            # 1. Send session.start
            start_msg = {
                "type": "session.start",
                "session_id": session_id,
                "source": "simulator",
                "format": {
                    "sampleRate": SAMPLE_RATE,
                    "channels": 1,
                    "encoding": "PCM_16"
                }
            }
            await ws.send(json.dumps(start_msg))
            logger.info("Sent session.start")

            # 2. Wait for session.started confirmation
            response = await ws.recv()
            logger.info(f"Gateway Response: {response}")

            # 3. Stream audio in chunks
            with open(filepath, "rb") as f:
                # Skip WAV header (approx 44 bytes) for simplicity
                f.seek(44)
                
                chunk_size = CHUNK_DURATION_MS * BYTES_PER_MS
                
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    
                    await ws.send(data)
                    logger.info(f"Sent {len(data)} bytes")
                    
                    # Simulate real-time streaming wait
                    await asyncio.sleep(CHUNK_DURATION_MS / 1000.0)

            # 4. Send session.stop
            stop_msg = {
                "type": "session.stop",
                "session_id": session_id
            }
            await ws.send(json.dumps(stop_msg))
            logger.info("Sent session.stop")
            
            response = await ws.recv()
            logger.info(f"Gateway Response: {response}")

    except Exception as e:
        logger.error(f"WebSocket Error: {e}")

async def main():
    wav_files = list(AUDIO_DIR.glob("*.wav"))
    if not wav_files:
        logger.error(f"No WAV files found in {AUDIO_DIR}")
        return

    logger.info(f"Found {len(wav_files)} test audio files.")
    
    try:
        while True:
            file_to_play = random.choice(wav_files)
            await stream_audio_file(file_to_play)
            
            # Wait a few seconds before the next simulated call
            wait_time = random.uniform(3.0, 7.0)
            logger.info(f"Call ended. Waiting {wait_time:.1f}s before next call...\n")
            await asyncio.sleep(wait_time)
            
    except KeyboardInterrupt:
        logger.info("Simulator stopped.")

if __name__ == "__main__":
    asyncio.run(main())
