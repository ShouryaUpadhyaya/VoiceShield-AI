#!/usr/bin/env python3
"""
Convert Dataset Script

Recursively scans the input directory for all audio files (.aac, .mp3, .m4a, .ogg)
and converts them into 48kHz, mono, PCM16 WAV files using FFmpeg.
The converted files are saved to the output directory while preserving the original folder structure.
This ensures no recordings are missed and all are compatible with the Android simulator.
"""

import os
import sys
import subprocess
from pathlib import Path

SUPPORTED_EXTS = {".aac", ".mp3", ".m4a", ".ogg", ".flac"}

def convert_dataset(input_dir: str, output_dir: str):
    in_path = Path(input_dir)
    out_path = Path(output_dir)

    if not in_path.exists():
        print(f"Error: Input directory '{in_path}' does not exist.")
        sys.exit(1)

    out_path.mkdir(parents=True, exist_ok=True)

    print(f"Scanning '{in_path}' for audio files...")
    
    # Track statistics
    found = 0
    converted = 0
    failed = 0
    skipped = 0

    # Recursively find all files
    for file_path in in_path.rglob("*"):
        if not file_path.is_file():
            continue

        ext = file_path.suffix.lower()
        if ext not in SUPPORTED_EXTS and ext != ".wav":
            continue

        found += 1

        # Calculate relative path to maintain folder structure
        rel_path = file_path.relative_to(in_path)
        
        # Determine output path (change extension to .wav)
        out_file = out_path / rel_path.with_suffix('.wav')

        if out_file.exists():
            print(f"[SKIPPED] Already exists: {out_file.name}")
            skipped += 1
            continue

        # Ensure output subdirectories exist
        out_file.parent.mkdir(parents=True, exist_ok=True)

        print(f"[CONVERTING] {rel_path} -> {out_file.name}")
        
        # FFmpeg command to convert to 48kHz, mono, PCM s16le
        cmd = [
            "ffmpeg",
            "-y",                   # Overwrite output files
            "-i", str(file_path),   # Input file
            "-c:a", "pcm_s16le",    # Audio codec: PCM 16-bit little-endian
            "-ar", "48000",         # Audio sample rate: 48kHz
            "-ac", "1",             # Audio channels: 1 (mono)
            "-loglevel", "error",   # Hide verbose ffmpeg output
            str(out_file)           # Output file
        ]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                converted += 1
            else:
                print(f"[FAILED] Error converting {file_path.name}: {result.stderr.decode()}")
                failed += 1
        except Exception as e:
            print(f"[FAILED] Exception converting {file_path.name}: {e}")
            failed += 1

    print("\n" + "="*40)
    print("CONVERSION COMPLETE")
    print("="*40)
    print(f"Total audio files found: {found}")
    print(f"Successfully converted:  {converted}")
    print(f"Skipped (already wav):   {skipped}")
    print(f"Failed conversions:      {failed}")
    print("="*40)
    print(f"Your ready-to-test dataset is in: {out_path.absolute()}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python convert_dataset.py <INPUT_DIR> <OUTPUT_DIR>")
        print("Example: python convert_dataset.py DATA_SET_DONT_PUSH data/wavs")
        sys.exit(1)

    convert_dataset(sys.argv[1], sys.argv[2])
