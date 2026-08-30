# VoiceShield AI

VoiceShield is an advanced real-time voice verification and deepfake detection system. It seamlessly integrates a robust Node.js media gateway, a high-performance FastAPI ML inference backend, and a modern Next.js frontend to monitor live telephony calls. By intercepting live calls and streaming audio chunks asynchronously, VoiceShield detects synthetic voices and spoofing attempts without interrupting the user.

## Key Features

- **Real-Time Chunking**: The media gateway intercepts raw PCM telephony streams from an Android device (via CallVault daemon) and forwards audio chunks (3 seconds) asynchronously to the ML pipeline.
- **Deepfake Detection Models**: Powerful PyTorch models (Dhwani & ECAPA) evaluate deepfake probabilities and verify speaker enrollments.
- **Live Dashboard**: Watch chunk processing, VAD, RMS Energy Waveforms, and Spectrograms in real-time on the Next.js/React frontend via WebSocket/SSE integration.
- **PostgreSQL Persistence**: Comprehensive call records, raw chunks, and ML scores are securely saved for analysis.
- **Android Integration**: Native integration with CallVault (privileged daemon on Android) to intercept audio streams directly at the OS level.
- FreeSWITCH Integration**: Handles SIP signaling and streams raw PCM audio into the ML backend.

---

## Download CallVault (Android)

You can download the latest debug build of the VoiceShield CallVault daemon for Android devices here:
**[Download VoiceShield-CallVault-Debug.apk (v1.0.0)](https://github.com/ShouryaUpadhyaya/VoiceShield-AI/raw/main/releases/VoiceShield-CallVault-Debug.apk)**

---

## Prerequisites

Before starting, make sure you have:
- Node.js (v18+)
- Python (3.10+)
- PostgreSQL Database
- Docker & Docker Compose (for Media Gateway testing with FreeSWITCH)

---

## Detailed Setup Instructions

The system consists of three main components: Database & Media Gateway, ML Service, and the Frontend Dashboard. Follow these steps in order.

### 1. Database & Media Gateway (Node.js)

The Media Gateway (port 8010) receives WebSocket audio streams, chunks them, and manages session state.

```bash
cd media-gateway

# Set up Prisma ORM
npx prisma db push
npx prisma generate

# Install dependencies
npm install

# Start the Gateway in development mode
npm run dev
```

### 2. Machine Learning Service (Python / FastAPI)

The ML service (port 8000 / 8011) processes audio chunks and runs deepfake inference using PyTorch.

```bash
# From the VoiceShield-AI root directory
python3 -m venv .venv
source .venv/bin/activate

# Install requirements with CUDA 12.6 support (if using GPU)
pip install --extra-index-url https://download.pytorch.org/whl/cu126 -r ml/requirements-torch.txt

# Start the ML Backend (ensure PYTHONPATH includes the root to locate `ml` models)
cd backend
PYTHONPATH=.. uvicorn app.main:app --host 0.0.0.0 --port 8000
```
> Note: If you have a separate ML WebSocket endpoint for inference, it typically runs on port 8011.

### 3. Frontend Dashboard (Next.js)

The interactive dashboard (port 3000 or 8085 depending on config) displays real-time results, visualizations, and session logs.

```bash
# From the VoiceShield-AI root directory
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

### 4. CallVault Android App Setup

CallVault does not require Shizuku or a PC to intercept telephony audio. It establishes a local persistent privileged daemon entirely on-device by talking directly to your phone's internal Wireless Debugging port.

1. Enable **Developer Options**, then **Wireless Debugging**, on your Android device.
2. Install and open the CallVault app (see the Download section above).
3. Follow the onboarding wizard:
   - Grant **notifications** (required to see the pairing prompt).
   - Complete the **one-time Wireless Debugging pairing** by entering the pairing code and port shown in your Android settings.
   - Grant the remaining permissions (phone state, call log, contacts, battery exemption).
4. Accept the **USB debugging** prompt when onboarding offers it. CallVault will then automatically handle keeping the necessary services alive without requiring a cable.

---

## Testing & Verification

### Unit & Integration Tests

The Media Gateway includes an extensive test suite (50+ passing tests covering chunking, protocol validation, and session management).

```bash
cd media-gateway
npm run test
```

### Using the Android Simulator

If you don't have a physical Android device running CallVault, you can use the built-in Android Simulator to test the complete pipeline (Android -> Gateway -> ML Server -> Database -> Frontend).

The simulator streams audio over WebSockets precisely like the real Android daemon.

```bash
# From the VoiceShield-AI root directory
source .venv/bin/activate

# Stream a single specific audio file
python tests/integration/test_android_simulator.py /path/to/audio/file.wav

# Stream all files in a directory sequentially
python tests/integration/test_android_simulator.py /path/to/audio/directory/

# Run with a built-in default sample (librosa trumpet)
python tests/integration/test_android_simulator.py
```
*Note: Make sure your Media Gateway is running on port 8010 before executing the simulator.*

### Testing with FreeSWITCH (External/Echo Mode)

You can also test the media gateway and DSP visualizations using SIP.

1. Ensure the Docker containers are running (`docker-compose -f docker-compose.yml up -d`).
2. Open a SIP Client (like Linphone) on the same Wi-Fi network.
3. Dial `sip:test_call@<YOUR_LAPTOP_IP>:5060`.
4. Speak into your microphone and view live RMS/Spectrogram graphs on the dashboard.

---

## Architecture Overview

1. **Android Phone / CallVault** captures live 48kHz mono PCM16 audio.
2. **WebSocket (ws://<laptop-IP>:8010)** streams audio to the **Media Gateway**.
3. **Media Gateway** buffers and slices audio into precise 3-second chunks (288,000 bytes).
4. **ML Service (ws://localhost:8011)** receives the chunks and executes PyTorch inference.
5. **Dashboard** listens via WebSockets/SSE to visualize results and flag potential fraud instantly.

For a deep dive into the architecture and dynamic SIP Trunk routing, refer to [Media Gateway Documentation](media_gateway_documentation.md) and `STATUS.md`.
