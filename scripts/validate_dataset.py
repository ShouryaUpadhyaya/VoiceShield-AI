import os
import wave
import argparse
import numpy as np
import scipy.io.wavfile as wavfile
from pathlib import Path

def validate_dataset(input_dir, output_report):
    input_dir = Path(input_dir)
    output_report = Path(output_report)
    output_report.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_report, "w", encoding="utf-8") as f:
        f.write("filepath,valid,sample_rate,channels,duration,rms,peak,corruption_status\n")
        
        valid_count = 0
        invalid_count = 0
        
        for root, dirs, files in os.walk(input_dir):
            for filename in files:
                if filename.lower().endswith(".wav"):
                    filepath = Path(root) / filename
                    
                    try:
                        # Basic header validation
                        with wave.open(str(filepath), 'rb') as w:
                            rate = w.getframerate()
                            channels = w.getnchannels()
                            frames = w.getnframes()
                            duration = frames / float(rate)
                            
                        # Signal validation
                        sr, data = wavfile.read(str(filepath))
                        
                        if len(data) == 0:
                            raise ValueError("Empty audio data")
                            
                        if not np.isfinite(data).all():
                            raise ValueError("NaN or Inf in audio data")
                            
                        if data.dtype == np.int16:
                            data_float = data.astype(np.float32) / 32768.0
                        else:
                            data_float = data.astype(np.float32)
                            
                        rms = np.sqrt(np.mean(data_float**2))
                        peak = np.max(np.abs(data_float))
                        
                        if rms < 1e-5:
                            raise ValueError("RMS too low (silent)")
                            
                        valid_count += 1
                        f.write(f"{filepath},True,{rate},{channels},{round(duration, 3)},{rms:.4f},{peak:.4f},OK\n")
                        
                    except Exception as e:
                        invalid_count += 1
                        f.write(f"{filepath},False,0,0,0,0,0,{str(e)}\n")
                        print(f"Validation failed for {filepath}: {e}")

    print("\n--- VALIDATION SUMMARY ---")
    print(f"Total checked: {valid_count + invalid_count}")
    print(f"Valid: {valid_count}")
    print(f"Invalid: {invalid_count}")
    print(f"Report written to {output_report}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="data/wavs/fake")
    parser.add_argument("--report", type=str, default="data/metadata/validation_report.csv")
    
    args = parser.parse_args()
    validate_dataset(args.input, args.report)
