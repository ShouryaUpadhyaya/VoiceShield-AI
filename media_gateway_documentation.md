# VoiceShield AI - Media Gateway Architecture & Implementation Guide

## 1. Overview & What It Does For You
The VoiceShield AI Media Gateway acts as the "Ears" of the fraud prevention system. 
In a real-world scenario, when a scammer calls a user's phone, their telecom provider routes the call through our FreeSWITCH instance. The Gateway intercepts these live telecom calls and streams a real-time copy of the audio to our AI processing nodes, while simultaneously connecting the caller to their destination. 

This allows VoiceShield to run its Deepfake detection models, analyze prosody, and flag synthetic voices instantly—all without delaying or interrupting the actual phone call!

## 2. Tech Stack & Technologies Used

### Core Telecom Engine
- **FreeSWITCH (C/C++)**: A highly scalable software-defined telecom stack. It handles all SIP signaling, RTP media streaming, and bridging. It operates in Docker using `network_mode: "host"` to natively bind to the server's network interfaces, seamlessly navigating NAT issues.

### AI Processing Backend
- **Python Backend (`test_media_pipeline.py`)**: Built with **FastAPI**, **Uvicorn**, and **Pydantic**.
- **NumPy**: Used for high-speed Digital Signal Processing (DSP).
- **FreeSWITCH Event Socket Layer (ESL)**: Used via TCP (port 8021) to hot-reload configurations dynamically without restarting the server.

### Real-Time Visualization Frontend
- **React + Vite + TypeScript**: Modern frontend ecosystem.
- **Shadcn UI & Tailwind CSS**: Premium, dark-mode component library used for building sleek, responsive dashboard interfaces.
- **Recharts**: For rendering the live RMS Energy Waveform.
- **HTML5 Canvas**: For rendering the high-performance Spectrogram matrix.

## 3. Communication Protocols

- **SIP (Session Initiation Protocol - Port 5060)**: Used by FreeSWITCH to establish, modify, and terminate calls with clients (like Linphone) or external trunks (like Twilio).
- **RTP (Real-time Transport Protocol - Ports 16384-16484)**: Used to carry the actual voice audio data over UDP.
- **WebSockets (Port 8005)**: Used by FreeSWITCH (`mod_audio_stream`) to stream raw `16kHz PCM mono` audio bytes directly into the Python AI backend in real-time.
- **Server-Sent Events (SSE - Port 8005)**: Used by the Python backend to push live metrics (VAD, Spectrogram matrices, RMS) to the React frontend. SSE is highly efficient for unidirectional real-time data streaming.

## 4. Features Implemented

1. **Live DSP Visualizations**: The frontend translates raw audio bytes into three graphs:
   - **Waveform (RMS)**: Shows raw audio energy/volume.
   - **Spectrogram (FFT)**: Converts audio into frequency bins to visualize pitch/tone using an HTML5 Canvas.
   - **VAD (Speech Activity)**: A timeline that distinguishes between human speech and silence.
2. **WebSocket Stability**: The Python loop handles graceful disconnects (`websocket.disconnect`) to prevent server crashes when calls drop.
3. **Dynamic IP Networking**: By binding FreeSWITCH to the host network natively, you never need to manually hardcode your Wi-Fi IP in XML files for local testing. It dynamically detects the host's LAN IP.
4. **Dynamic External Routing UI**: A Shadcn configuration tab that accepts SIP Trunk credentials, generates FreeSWITCH XML configurations on the fly, and uses ESL to hot-reload the changes instantly!

## 5. How to Test the Gateway

### Internal Testing (Echo Mode)
1. Ensure the Docker containers (`freeswitch`, `media-tester`, `frontend`) are running.
2. Open the Linphone app on your mobile device (ensure it's on the same Wi-Fi as your laptop).
3. Dial `sip:test_call@<YOUR_LAPTOP_IP>:5060`.
4. Open the Dashboard at `http://localhost:8085/media-logs`.
5. Talk into your phone and watch the live Spectrogram and Waveform react!

### External Trunk Routing (e.g. Twilio)
To route the call to a real-world phone number:
1. Open the Dashboard at `http://localhost:8085/media-logs`.
2. Click the **External Routing** tab.
3. Select **"External Trunk Bridge"**.
4. (Optional) Check **"Use Manual IP Override"** and enter your laptop's Wi-Fi IP if FreeSWITCH struggles to auto-detect it.
5. Enter your SIP trunk Provider Name, Username, Password, and Domain.
6. Click **Save & Hot-Reload**. FreeSWITCH will apply the new routing rules instantly. Calling `sip:test_call@...` will now route out to the real world while streaming audio to the dashboard!
