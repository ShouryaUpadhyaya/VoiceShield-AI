import os
import glob
import random
import numpy as np
import librosa
from pathlib import Path
from collections import defaultdict
from ml.adapters.dhwani import load_dhwani, run

def evaluate_dataset():
    print("Loading Dhwani model...")
    if not load_dhwani():
        print("Failed to load Dhwani.")
        return

    results = defaultdict(list)
    
    # Collect all audio files
    base_dir = Path("data/wavs")
    all_files = list(base_dir.rglob("*.wav")) + list(base_dir.rglob("*.flac"))
    
    # Group by category
    categories = defaultdict(list)
    for file in all_files:
        path_str = str(file)
        if "fake/easy" in path_str:
            cat = "Fake (Easy)"
        elif "fake/medium" in path_str:
            cat = "Fake (Medium)"
        elif "fake/hard" in path_str:
            cat = "Fake (Hard)"
        elif "fake" in path_str:
            cat = "Fake (Edge-TTS)"
        elif "real" in path_str:
            cat = "Real"
        else:
            cat = "Unknown"
        categories[cat].append(file)
        
    print(f"Found {len(all_files)} total audio files. Sampling up to 20 files per category...")
    
    for cat, files in categories.items():
        if len(files) > 20:
            files = random.sample(files, 20)
            
        print(f"\nEvaluating category: {cat} ({len(files)} files)")
        for file in files:
            try:
                audio, sr = librosa.load(file, sr=16000, mono=True)
                chunk_samples = 16000 * 3
                probs = []
                for start in range(0, min(len(audio), chunk_samples*3), chunk_samples):
                    chunk = audio[start:start+chunk_samples]
                    if len(chunk) < chunk_samples:
                        chunk = np.pad(chunk, (0, chunk_samples - len(chunk)), mode='constant')
                    res = run(chunk)
                    if res:
                        probs.append(res['synthetic_probability'])
                if probs:
                    max_prob = max(probs)
                    results[cat].append(max_prob)
            except Exception as e:
                print(f"Error processing {file}: {e}")
                
    # Print Summary
    print("\n" + "="*50)
    print("Dhwani Evaluation Results (Sampled Max Chunk Probability)")
    print("="*50)
    for category, probs in results.items():
        if not probs: continue
        mean_prob = np.mean(probs)
        median_prob = np.median(probs)
        # Accuracy: threshold 0.5. Real files should be < 0.5, Fake should be > 0.5
        correct = [p > 0.5 for p in probs] if "Fake" in category else [p < 0.5 for p in probs]
        accuracy = np.mean(correct) * 100
        
        print(f"Category: {category}")
        print(f"  Count:    {len(probs)} files")
        print(f"  Mean:     {mean_prob*100:.1f}%")
        print(f"  Median:   {median_prob*100:.1f}%")
        print(f"  Accuracy: {accuracy:.1f}%")
        print("-" * 50)

if __name__ == "__main__":
    evaluate_dataset()
