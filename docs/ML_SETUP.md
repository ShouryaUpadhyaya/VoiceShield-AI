# VoiceShield ML Pipeline Setup

## Prerequisites
- Python 3.14+
- `librosa`, `parselmouth`, `soxr`, `torch`, `speechbrain`, `onnxruntime`, `fastapi`, `uvicorn`, `websockets`

## Installation
Use the provided `requirements.txt`:
```bash
pip install -r requirements.txt
```

Note: for PyTorch CPU, use the specific index url for your platform.

## Model Setup
The service gracefully starts even if models are missing, reporting them as UNAVAILABLE in `/ready`.

### 1. Dhwani
HuggingFace repo: `ayush2635/Dhwani-Multilingual-Deepfake-Audio-Detection-Model`
Download `best_model.onnx` into `models/dhwani/dhwani.onnx`.

### 2. ECAPA Speaker Verification
HuggingFace repo: `speechbrain/spkrec-ecapa-voxceleb`
This model will download its required files automatically on first inference, saving them to `models/ecapa/`.

### 3. Custom Deepfake
Place your trained checkpoint in `artifacts/<experiment>/best.pt`. The service picks up the latest one automatically.

## Running the Server
Start the FastAPI server (default: port 8011):
```bash
python -m ml.server.main
```

Check health:
```bash
curl http://localhost:8011/health
curl http://localhost:8011/ready
```
