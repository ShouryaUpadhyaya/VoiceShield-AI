import os
import wave
import json
import argparse
from pathlib import Path

def inspect_dataset(input_dir, output_manifest):
    input_dir = Path(input_dir)
    output_manifest = Path(output_manifest)
    
    # Ensure output directory exists
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    
    processed = 0
    errors = 0
    
    print(f"Inspecting WAV files in {input_dir}")
    with open(output_manifest, "w", encoding="utf-8") as f:
        for root, dirs, files in os.walk(input_dir):
            for filename in files:
                if filename.lower().endswith(".wav"):
                    filepath = Path(root) / filename
                    
                    try:
                        with wave.open(str(filepath), 'rb') as w:
                            frames = w.getnframes()
                            rate = w.getframerate()
                            channels = w.getnchannels()
                            duration = frames / float(rate)
                            
                        # Basic metadata
                        # We don't have transcripts yet, so we set transcript_available=False
                        # Language is assumed unknown for now
                        record = {
                            "original_path": str(filepath.absolute()),
                            "original_name": filename,
                            "duration_seconds": round(duration, 3),
                            "sample_rate": rate,
                            "channels": channels,
                            "format": "wav",
                            "language": None,
                            "speaker_count_estimate": "unknown", # Will need diarization later
                            "transcript_available": False,
                            "has_speech": True, # Assume true for now, can be refined with VAD
                            "status": "eligible"
                        }
                        
                        f.write(json.dumps(record) + "\n")
                        processed += 1
                        
                    except Exception as e:
                        print(f"Error processing {filepath}: {e}")
                        errors += 1
                        record = {
                            "original_path": str(filepath.absolute()),
                            "original_name": filename,
                            "status": "invalid"
                        }
                        f.write(json.dumps(record) + "\n")
                        
    print(f"Inspection complete. Processed: {processed}, Errors: {errors}")
    print(f"Manifest written to {output_manifest}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect real dataset and generate manifest")
    parser.add_argument("--input", type=str, required=True, help="Path to input directory containing real WAVs")
    parser.add_argument("--output", type=str, default="data/metadata/real_manifest.jsonl", help="Path to output manifest")
    
    args = parser.parse_args()
    inspect_dataset(args.input, args.output)
