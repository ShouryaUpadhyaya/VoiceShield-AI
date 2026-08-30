# Indic Deepfake Detection

VoiceShield-AI now integrates a highly specialized **Indic Deepfake Detector** tuned specifically for spoofed and AI-generated speech in Indic languages and accents.

## Architecture

The Indic detector is based on the **RawNet2** architecture. Unlike traditional spectral feature extraction (like MFCCs), it operates directly on the raw audio waveform using a pre-emphasis filter and a Sinc-convolutional layer.

1. **Input Format**: 16 kHz, mono, 32-bit float PCM.
2. **Padding**: The model expects fixed-length sequences (64,600 samples or ~4 seconds). Our 3-second chunks (48,000 samples) are zero-padded internally by the detector adapter to match this dimensionality.
3. **Output**: The network yields log-softmax scores for `[genuine, spoof]`. We convert these back to linear probabilities, returning a `fake_probability` (0.0 to 1.0).

## Pipeline Integration

The detector runs seamlessly alongside the other inference engines in the local Python ML service (`ml/`):
- It is instantiated as a singleton on service startup via `ml.adapters.indic`.
- It processes every 3-second audio chunk passed over the WebSocket from the Media Gateway.
- If the model checkpoint (`voiceshield-indic-v0.1.pth`) is missing, the adapter logs a warning and gracefully degrades; the model is marked as `UNAVAILABLE` and is excluded from the final AI likelihood fusion.

## Model Weights (Git LFS)

The model checkpoint is located at `ml/deepfake_detection/indic/frozen/voiceshield-indic-v0.1.pth` and is managed via Git LFS. If inference fails with a size error, ensure that Git LFS has successfully pulled the binary file and not just the text pointer.

```bash
git lfs pull
```
