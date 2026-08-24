# Media Gateway Pipeline Documentation

## 1. Overview and Project Relation
The Media Gateway Pipeline is a critical sub-system of the VoiceShield AI platform. Its primary responsibility is to bridge standard telecommunications protocols (SIP/RTP) to the modern, real-time web infrastructure required by our AI models.

When a potential victim receives a call from an attacker, the call routes through our FreeSWITCH media gateway. Instead of just passing the audio through, FreeSWITCH uses a custom C-module (`mod_audio_stream`) to asynchronously "fork" a copy of the audio and transmit it in real-time over WebSockets to our Python analysis engine.

### How it relates to the whole project:
- **Feeds the Deepfake Engine**: Provides the raw 16kHz L16 PCM audio chunks required by the PyTorch ML models.
- **Feeds the DSP Engine**: Provides the identical audio stream for audio artifact detection.
- **Feeds the Risk Engine**: Extracts Call-ID, Caller ID, and Callee ID from the SIP metadata and provides it to the risk scoring pipeline.
- **Empowers the Frontend**: The backend combines the ML inferences with the SIP metadata and broadcasts it to the React frontend, allowing the end user to see exactly who is calling and whether the voice is synthetic.

## 2. Specific Implementation Details
- **FreeSWITCH Dockerized**: The gateway runs in a dedicated Docker container (`drachtio-freeswitch-mrf` base) orchestrated by `docker-compose.media.yml`.
- **Dialplan Configuration**: Located in `infrastructure/freeswitch/conf/freeswitch.xml`, the dialplan answers inbound calls and immediately triggers `uuid_audio_stream`.
- **WebSocket Streaming**: 
  - Host: `ws://media-tester:8005/api/analyze-stream`
  - Audio Format: Mono, 16000 Hz, L16 PCM
  - Metadata: Passed securely in the WebSocket HTTP upgrade handshake using `x-call_id`, `x-caller`, and `x-callee` headers.
- **Media Tester**: A standalone FastAPI python server (`test_media_pipeline.py`) simulating the AI Backend to validate the media pipeline.
- **Frontend Live Viewer**: Live logs of the testing pipeline are presented via SSE on the React frontend at `/media-logs`.

## 3. How to Test It Manually

To manually verify the media pipeline with a real device (mobile or laptop):

### Prerequisites
1. Start the media pipeline using Docker Compose:
   ```bash
   docker-compose -f docker-compose.media.yml up -d --build
   ```
2. Start the Frontend UI:
   ```bash
   docker-compose up -d frontend
   ```
3. Find your computer's local IP address (e.g., `192.168.1.100`).

### Execution
1. **Download a SIP Client**:
   - For Mobile (iOS/Android): Download **Linphone** or **Zoiper**.
   - For Laptop (Windows/Mac): Download **MicroSIP** or **Linphone**.
2. **Make the Call**:
   - Open your SIP client app. No account setup or registration is needed.
   - Dial the SIP URI targeting your FreeSWITCH container using your host IP:
     `sip:test_call@<YOUR_LOCAL_IP>:5060`
     *(Example: `sip:test_call@192.168.1.100:5060`)*
3. **Verify the Results**:
   - FreeSWITCH will answer the call instantly. You will hear an echo of your voice confirming the call is active.
   - Navigate to the Frontend UI at `http://localhost:8085/media-logs`.
   - You will see real-time logs indicating your SIP call connected, the WebSocket handshake completed, and the exact byte count of your real voice being streamed to the server.
   - Hang up the softphone to gracefully terminate the stream.

## 4. Use Cases
- **Enterprise PBX Integration**: A company can configure their existing PBX (like Asterisk or Cisco CallManager) to route calls through VoiceShield's FreeSWITCH gateway via a SIP Trunk.
- **Telecom Carrier Peering**: Telecom operators can integrate VoiceShield at the carrier level using an SBC (Session Border Controller) communicating directly with our FreeSWITCH node.
- **Consumer Mobile App**: Users on a mobile VoIP application (WebRTC or SIP) can have their calls routed through the media gateway to receive real-time deepfake alerts on their smartphone screens.
