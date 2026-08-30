#!/usr/bin/env bash
# One-time setup: fetch all pretrained weights VoiceShield needs.
set -e
mkdir -p models/dhwani

echo "[1/3] Silero VAD -> cached automatically via torch.hub on first run (no manual step)."

echo "[2/3] Dhwani ONNX deepfake detector..."
python - << 'PY'
import os
from huggingface_hub import hf_hub_download
path = hf_hub_download(repo_id="ayush2635/Dhwani-Multilingual-Deepfake-Audio-Detection-Model", filename="best_model.onnx", local_dir="models/dhwani")
# Rename it to dhwani.onnx for the pipeline to find it
if os.path.exists("models/dhwani/best_model.onnx"):
    os.rename("models/dhwani/best_model.onnx", "models/dhwani/dhwani.onnx")
print("Saved Dhwani ONNX model.")
PY

echo "[3/3] ECAPA-TDNN -> cached automatically by SpeechBrain on first run (no manual step)."

echo "Done. Verify models/dhwani/dhwani.onnx exists (~1.26GB)."
