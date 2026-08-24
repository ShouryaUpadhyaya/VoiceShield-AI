import asyncio
import websockets
import json
import sys
import os
import time

async def simulate_call(file_path: str, ws_url: str = "ws://localhost:8000/api/analyze-stream"):
    """
    Simulates a live telephony call by chunking an audio file and streaming it
    to the VoiceShield AI backend over a WebSocket.
    """
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        sys.exit(1)

    print(f"Connecting to {ws_url}...")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print("Connected! Streaming audio chunks...")
            
            # Read the whole file for simplicity in simulation,
            # then send it in chunks. In a real system, you'd stream live PCM.
            with open(file_path, "rb") as f:
                data = f.read()
                
            # Simulate chunks. For a WAV file, blindly chunking might break headers if done naively,
            # but since our backend is just doing `analyze_deepfake(stream, data)`, it might
            # try to decode each chunk as an independent file. 
            # In a production WebSocket stream, we'd send raw PCM and the backend would maintain 
            # a rolling buffer. 
            # For this MVP simulation, we'll send the entire file or large chunks.
            # We'll send it in one go to trigger the risk engine for the demo.
            
            print(f"Sending {len(data)} bytes of audio data...")
            await websocket.send(data)
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                result = json.loads(response)
                print("\n--- Live Risk Analysis Report ---")
                print(f"Deepfake Probability: {result['signals']['deepfake_probability'] * 100:.1f}%")
                print(f"Risk Score: {result['risk_assessment']['risk_score']}%")
                print(f"Risk Level: {result['risk_assessment']['risk_level']}")
                print(f"Prevention Action: {result['prevention_status']['status']}")
                print("---------------------------------")
                
            except asyncio.TimeoutError:
                print("Error: No response from server.")
            
    except ConnectionRefusedError:
        print(f"Connection refused. Is the FastAPI server running at {ws_url}?")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python simulate_call.py <path_to_audio.wav>")
        sys.exit(1)
        
    asyncio.run(simulate_call(sys.argv[1]))
