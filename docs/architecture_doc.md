# VoiceShield Architecture: Media Pipeline & ML Integration

## Overview
VoiceShield protects against deepfake voice calls and unauthorized access using a real-time audio analysis pipeline.

The architecture is composed of:
1. **Media Gateway (Node.js/Prisma)**: Integrates with telephony (e.g., FreeSWITCH), chunks real-time PCM audio, and communicates with the ML backend via WebSocket.
2. **ML Backend (FastAPI)**: Receives streaming audio, buffers it, and continuously runs `dhwani` (deepfake detection), `ecapa` (speaker verification), and prosody models over sliding windows.
3. **Frontend (Next.js)**: Displays a real-time dashboard of calls and their chunk-by-chunk processing statuses and ML scores using WebSockets.

## Media Pipeline Flow
1. A call starts and `test_media_pipeline.py` (or FreeSWITCH) connects to `media-gateway` or directly via WebSocket.
2. The Gateway's `chunker.ts` splits incoming continuous raw audio into fixed millisecond blocks (e.g., 3-second blocks, 500ms hops).
3. The `MlClient` (in `ml-client.ts`) wraps each chunk in a metadata frame (JSON) followed by the binary audio (PCM) and sends it to `/api/analyze-stream`.
4. `stream.py` inside the FastAPI ML backend collects the data, processes it via PyTorch models, and returns JSON `score` messages.
5. The `MlClient` receives the score, saves it into PostgreSQL (`ml_results` table) using Prisma (`persistence.ts`), and updates the chunk's `processing_progress`.
6. `server.ts` broadcasts the result via `dashboardIo` (`socket.io`) to the Next.js frontend, updating the UI live.

## Database Schema Highlights
- `audio_chunks`: Tracks sequence number, bytes, and `processing_progress`.
- `ml_results`: Stores model-specific data like `is_deepfake`, `speaker_id`, and raw JSON output for latency/debugging.

## ML Pipeline Limitations & FAQ

### Why is the Deepfake Probability 0.0% for some Fake Audio?
VoiceShield currently uses the **Dhwani (AASIST/XLS-R)** model as its primary generic anti-spoofing detector. While highly accurate at detecting traditional Text-To-Speech (TTS) and older Voice Conversion (VC) artifacts, it struggles against **High-Fidelity Neural Vocoders** (e.g., `hifigan_autoencoder`).

**The Technical Reason:**
Deepfake audio is generated in two steps:
1. An acoustic model generates a mel-spectrogram.
2. A **Vocoder** converts the spectrogram into an actual audio waveform.

Traditional vocoders (like Griffin-Lim) leave distinct phase distortions and spectral artifacts that Dhwani easily detects (flagging them as 99.9% fake). However, state-of-the-art neural vocoders (like HiFi-GAN) perfectly reconstruct phase continuity and glottal patterns. This effectively scrubs the synthetic artifacts from the waveform, tricking baseline anti-spoofing models like Dhwani into evaluating the audio as real human speech (0.0% synthetic probability).

**Mitigation:**
To catch these "hard" neural vocoder fakes, a specialized custom deepfake model must be trained on a dataset containing HiFi-GAN and neural vocoder artifacts. Once trained, the checkpoint should be placed in `artifacts/*/best.pt`, which the VoiceShield ML pipeline will automatically prioritize over Dhwani.
