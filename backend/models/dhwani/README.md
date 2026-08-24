# Dhwani Multilingual Deepfake Audio Detection Model

This directory is intended to house the Dhwani model in ONNX format. The Dhwani architecture is based on XLS-R and AASIST, optimized for real-time deepfake audio detection. 

## Model Requirements
- **Format**: ONNX
- **Input Channels**: 1 (Mono)
- **Input Sample Rate**: 16000 Hz
- **Input Type**: float32
- **Supported Languages**: English, Hindi, Tamil, Telugu, Malayalam

## Setup Instructions

1. Obtain the Dhwani `.onnx` model (e.g., `dhwani_model.onnx`).
2. Place the model file in this directory:
   ```bash
   cp dhwani_model.onnx backend/models/dhwani/
   ```
3. Set the required environment variable `DHWANI_MODEL_PATH` to point to the model file.

## Environment Variables

| Variable | Default Value | Description |
|---|---|---|
| `DHWANI_MODEL_PATH` | None | Absolute or relative path to the `.onnx` model file. |
| `DHWANI_EXECUTION_PROVIDER` | `CPUExecutionProvider` | ONNX runtime provider. Set to `CUDAExecutionProvider` for GPU acceleration if available. |
| `DHWANI_WINDOW_SECONDS` | `3.0` | Maximum audio duration per window. |
| `DHWANI_HOP_SECONDS` | `1.5` | Sliding window hop size for overlapping detection. |

*Note: Large model artifacts should not be committed to Git unless Git LFS is utilized. Therefore, this model file is excluded by standard `.gitignore` rules (if configured for `*.onnx`).*
