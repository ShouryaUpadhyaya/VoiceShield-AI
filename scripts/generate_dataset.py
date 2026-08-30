import os
import json
import yaml
import argparse
import random
import datetime
from pathlib import Path
import scipy.io.wavfile as wavfile
import numpy as np
import torch

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.channel.effects import process_channel
from src.transcription.whisper_transcriber import WhisperTranscriber

def load_config(config_path):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def load_manifest(manifest_path):
    records = []
    if not os.path.exists(manifest_path):
        return records
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def get_generator(model_config):
    name = model_config.get("name")
    if name in ["mms_tts_hin", "mms_tts_hin_vc"]:
        from src.generation.tts.mms_generator import MMSGenerator
        return MMSGenerator(model_config)
    elif name == "vocos_encodec":
        from src.generation.neural_vocoder.vocos_generator import VocosGenerator
        return VocosGenerator(model_config)
    else:
        from src.generation.tts.mock_generator import MockGenerator
        return MockGenerator(model_config)

def generate_dataset(input_dir, config_path, limit, dry_run, resume):
    config = load_config(config_path)
    real_manifest_path = "data/metadata/real_manifest.jsonl"
    fake_manifest_path = "data/metadata/fake_manifest.jsonl"
    failures_path = "data/metadata/generation_failures.jsonl"
    transcripts_dir = Path("data/metadata/transcripts")
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    
    real_records = load_manifest(real_manifest_path)
    if not real_records:
        print("Real manifest not found. Run inspect_dataset.py first.")
        return
        
    eligible = [r for r in real_records if r.get("status") == "eligible"]
    if limit:
        eligible = eligible[:limit]
        
    print(f"Total eligible inputs to process: {len(eligible)}")
    
    enabled_models = [m for m in config.get("models", []) if m.get("enabled", False)]
    difficulties = config.get("difficulties", {})
    variants = config.get("generation", {}).get("variants_per_model", 1)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    if dry_run:
        print("--- DRY RUN ---")
        return

    existing_fakes = set()
    if resume and os.path.exists(fake_manifest_path):
        with open(fake_manifest_path, "r") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    existing_fakes.add(rec["fake_path"])
                    
    # Initialize Transcriber
    print("Loading Transcriber...")
    transcriber = WhisperTranscriber(model_size="base", device=device)
                    
    generators = {}
    for m in enabled_models:
        gen = get_generator(m)
        gen.device = device
        gen.load_model()
        generators[m["name"]] = gen

    processed_count = 0
    skipped_count = 0
    failed_count = 0

    with open(fake_manifest_path, "a" if resume else "w", encoding="utf-8") as f_fake, \
         open(failures_path, "a" if resume else "w", encoding="utf-8") as f_fail:
         
        for record in eligible:
            original_name = record["original_name"]
            base_name = os.path.splitext(original_name)[0]
            audio_path = record["original_path"]
            
            transcript_path = transcripts_dir / f"{base_name}.json"
            transcript_text = None
            transcript_quality = "unknown"
            
            # Transcription step
            try:
                if transcript_path.exists():
                    with open(transcript_path, "r") as tf:
                        t_data = json.load(tf)
                        transcript_text = t_data["text"]
                        transcript_quality = "high"
                else:
                    t_result = transcriber.transcribe(audio_path)
                    transcript_text = t_result["text"]
                    transcript_quality = "high" if transcript_text else "low"
                    with open(transcript_path, "w") as tf:
                        json.dump(t_result, tf, indent=2)
            except Exception as e:
                print(f"Transcription failed for {original_name}: {e}")
                
            record["transcript_available"] = bool(transcript_text)
            
            for diff_name, diff_config in difficulties.items():
                for model_cfg in enabled_models:
                    model_name = model_cfg["name"]
                    family = model_cfg["family"]
                    
                    for variant in range(1, variants + 1):
                        variant_suffix = f"__v{variant:03d}" if variants > 1 else ""
                        fake_name = f"{base_name}__{diff_name}__{family}__{model_name}{variant_suffix}.wav"
                        
                        out_dir = Path(f"data/wavs/fake/{diff_name}/{family}/{model_name}")
                        out_dir.mkdir(parents=True, exist_ok=True)
                        fake_path = out_dir / fake_name
                        
                        if resume and str(fake_path) in existing_fakes:
                            skipped_count += 1
                            continue
                            
                        try:
                            gen = generators[model_name]
                            
                            # Prepare
                            prepared = gen.prepare_input(record, transcript=transcript_text)
                            
                            # Generate
                            waveform = gen.generate(prepared, config["generation"])
                            
                            # Channel processing
                            channel_ops = diff_config.get("channel_processing", [])
                            waveform, final_sr = process_channel(waveform, gen.sample_rate, channel_ops)
                            
                            # Save
                            wavfile.write(str(fake_path), final_sr, waveform)
                            
                            fake_meta = {
                                "synthetic": True,
                                "original_path": record["original_path"],
                                "original_name": original_name,
                                "fake_path": str(fake_path),
                                "fake_name": fake_name,
                                "difficulty": diff_name,
                                "generation_family": family,
                                "generation_method": model_name,
                                "model_version": "v1",
                                "reference_audio_path": record["original_path"],
                                "language": "en",
                                "duration_seconds": round(len(waveform)/final_sr, 3),
                                "original_sample_rate": record["sample_rate"],
                                "generated_sample_rate": final_sr,
                                "original_channels": record["channels"],
                                "generated_channels": 1,
                                "channel_condition": diff_config.get("channel_condition"),
                                "channel_processing": channel_ops,
                                "difficulty_reason": f"Generated using {model_name} with {diff_config.get('channel_condition')} channel.",
                                "transcript_available": record["transcript_available"],
                                "transcription_quality": transcript_quality,
                                "speaker_count": 1,
                                "random_seed": config["generation"]["random_seed"],
                                "generation_timestamp": datetime.datetime.now().isoformat(),
                                "status": "success"
                            }
                            f_fake.write(json.dumps(fake_meta) + "\n")
                            f_fake.flush()
                            processed_count += 1
                            print(f"Generated: {fake_name}")
                            
                        except Exception as e:
                            print(f"Error generating {fake_name}: {e}")
                            failed_count += 1
                            fail_meta = {
                                "original_name": original_name,
                                "generation_method": model_name,
                                "difficulty": diff_name,
                                "stage": "generation",
                                "error": str(e),
                                "timestamp": datetime.datetime.now().isoformat()
                            }
                            f_fail.write(json.dumps(fail_meta) + "\n")
                            f_fail.flush()

    print("\n--- GENERATION SUMMARY ---")
    print(f"Processed: {processed_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Failed: {failed_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--config", type=str, default="configs/generation.yaml")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    
    args = parser.parse_args()
    generate_dataset(args.input, args.config, args.limit, args.dry_run, args.resume)
