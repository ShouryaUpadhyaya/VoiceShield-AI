import os
import sys
import glob
import asyncio
from pathlib import Path
import subprocess
import edge_tts
from transformers import pipeline

# Use a small and fast whisper model with chunking for long audio
print("Loading Whisper model...")
asr = pipeline(
    "automatic-speech-recognition", 
    model="openai/whisper-tiny",
    chunk_length_s=30
)

def transcribe(audio_path: str) -> str:
    print(f"Transcribing {audio_path}...")
    result = asr(audio_path)
    text = result["text"].strip()
    print(f"Transcription: {text}")
    return text

async def generate_deepfake(text: str, output_path: str):
    # 'dada calls' implies a male Hindi/English speaker. Madhur is a male Hindi neural voice.
    # We can also use en-US-ChristopherNeural if preferred.
    voice = "hi-IN-MadhurNeural"
    print(f"Generating synthetic deepfake to {output_path} with voice {voice}...")
    communicate = edge_tts.Communicate(text, voice)
    
    # Save to MP3 first (edge-tts default)
    temp_mp3 = output_path.replace(".wav", ".mp3")
    await communicate.save(temp_mp3)
    
    # Convert mp3 to 16kHz mono WAV using ffmpeg so it seamlessly fits into the dataset
    subprocess.run([
        "ffmpeg", "-y", "-i", temp_mp3,
        "-ac", "1", "-ar", "16000",
        output_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Remove temp mp3
    if os.path.exists(temp_mp3):
        os.remove(temp_mp3)

async def process_dataset(input_dir: str, output_dir: str):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    audio_files = list(input_path.rglob("*.wav")) + list(input_path.rglob("*.flac")) + list(input_path.rglob("*.mp3"))
    if not audio_files:
        print(f"No audio files found in {input_dir}")
        return
        
    for file in audio_files:
        # Calculate relative path to mirror directory structure
        rel_path = file.relative_to(input_path)
        out_file = output_path / rel_path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        
        # We need output to be .wav
        out_file = out_file.with_suffix('.wav')
        
        # 1. Transcribe the real audio
        try:
            text = transcribe(str(file))
            if not text:
                print("Skipping (no speech detected).")
                continue
                
            # 2. Synthesize deepfake version
            await generate_deepfake(text, str(out_file))
            print(f"Successfully generated deepfake for {file.name}\n")
        except Exception as e:
            print(f"Failed to process {file}: {e}\n")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        in_dir = sys.argv[1]
        out_dir = sys.argv[2]
    else:
        # Defaults based on standard repo structure
        in_dir = "data/wavs/real"
        out_dir = "data/wavs/fake"
        
    print(f"Starting Deepfake generation pipeline...")
    print(f"Input Dir: {in_dir}")
    print(f"Output Dir: {out_dir}")
    
    asyncio.run(process_dataset(in_dir, out_dir))
    print("Done!")
