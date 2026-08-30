"""
Test script to send real audio from a WAV file through the ML Pipeline.
It simulates the Media Gateway chunking process (3-second 48kHz PCM16 chunks).

Usage:
  python ml/test_dataset_audio.py [path_to_audio.wav]
  
If no path is provided, it downloads a sample public domain speech file to test with.
"""
import asyncio
import json
import uuid
import sys
import os
import urllib.request
import numpy as np
import websockets
import soundfile as sf
import soxr

SAMPLE_URL = "https://www.voiptroubleshooter.com/open_speech/american/OSR_us_000_0010_8k.wav"
SAMPLE_FILE = "sample_speech.wav"

async def stream_audio_file(file_path: str):
    uri = "ws://localhost:8011/"
    session_id = str(uuid.uuid4())
    print(f"Starting simulated call {session_id} to {uri} using file: {file_path}")

    # Load audio file (convert to mono if stereo)
    audio, sr = sf.read(file_path)
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)

    print(f"Loaded audio: {len(audio)/sr:.2f} seconds at {sr}Hz")

    # The Gateway sends 48kHz PCM16. Resample the full audio to 48kHz first.
    if sr != 48000:
        print(f"Resampling from {sr}Hz to 48000Hz (Gateway format)...")
        audio_48k = soxr.resample(audio, sr, 48000, quality="HQ")
    else:
        audio_48k = audio

    # Gateway uses 3-second chunks (144,000 samples at 48kHz)
    chunk_samples = 48000 * 3
    total_chunks = int(np.ceil(len(audio_48k) / chunk_samples))

    overall_deepfake = []
    overall_prosody = []

    try:
        async with websockets.connect(uri) as ws:
            print("Connected to ML Server. Streaming chunks...")

            for seq in range(1, total_chunks + 1):
                start = (seq - 1) * chunk_samples
                end = min(seq * chunk_samples, len(audio_48k))
                chunk = audio_48k[start:end]

                # Convert to PCM16 LE bytes
                chunk_i16 = (chunk * 32767).astype("<i2")
                pcm_bytes = chunk_i16.tobytes()

                # Gateway metadata
                meta = {
                    "type": "audio.chunk",
                    "session_id": session_id,
                    "sequence": seq,
                    "timestamp_ms": (seq - 1) * 3000,
                    "duration_ms": int((len(chunk) / 48000) * 1000),
                    "sample_rate": 48000,
                    "channels": 1,
                    "encoding": "pcm_s16le",
                    "bytes": len(pcm_bytes)
                }

                await ws.send(json.dumps(meta))
                await ws.send(pcm_bytes)

                response = await ws.recv()
                result = json.loads(response)
                
                signals = result.get("signals", {})
                df_prob = signals.get("deepfake_probability")
                prosody = signals.get("prosody_analysis", {})
                anomaly = prosody.get("overall_prosody_risk") if prosody else None

                print(f"Chunk {seq}/{total_chunks}:")
                print(f"  Deepfake Prob: {df_prob*100:.1f}%" if df_prob is not None else "  Deepfake Prob: N/A")
                print(f"  Prosody Risk:  {anomaly*100:.1f}%" if anomaly is not None else "  Prosody Risk:  N/A")
                print(f"  Latency:       {result.get('inference_ms')} ms")

                if df_prob is not None:
                    overall_deepfake.append(df_prob)
                if anomaly is not None:
                    overall_prosody.append(anomaly)

                await asyncio.sleep(0.1) # Small delay
                
            print("\n--- FINAL CALL SCORE ---")
            if overall_deepfake:
                avg_df = sum(overall_deepfake) / len(overall_deepfake)
                print(f"Overall Deepfake Likelihood: {avg_df*100:.1f}%")
            if overall_prosody:
                avg_pr = sum(overall_prosody) / len(overall_prosody)
                print(f"Overall Prosody Anomaly:     {avg_pr*100:.1f}%")
            
    except ConnectionRefusedError:
        print("ERROR: Could not connect. Ensure the ML Server is running: python -m ml.server.main")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    import librosa
    # Use librosa's built-in example file if no file provided
    file_to_test = sys.argv[1] if len(sys.argv) > 1 else librosa.example('trumpet')
    
    if not os.path.exists(file_to_test):
        print(f"Test file '{file_to_test}' not found.")
        sys.exit(1)

    asyncio.run(stream_audio_file(file_to_test))
