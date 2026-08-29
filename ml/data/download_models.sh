#!/usr/bin/env bash
# One-time setup: fetch all pretrained weights VoiceShield needs.
set -e
mkdir -p models/dhwani

echo "[1/3] Silero VAD -> cached automatically via torch.hub on first run (no manual step)."

echo "[2/3] Dhwani ONNX deepfake detector..."
python - << 'PY'
from huggingface_hub import hf_hub_download
# Replace with the exact repo id / filename shown on the Dhwani model card.
path = hf_hub_download(repo_id="<ORG>/dhwani-deepfake-detector", filename="dhwani.onnx", local_dir="models/dhwani")
print("Saved:", path)
PY

echo "[3/3] ECAPA-TDNN -> cached automatically by SpeechBrain on first run (no manual step)."

echo "Done. Verify models/dhwani/dhwani.onnx exists (~1.26GB)."
