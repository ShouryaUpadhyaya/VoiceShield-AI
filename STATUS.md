# VoiceShield-AI Project Status

> Single source of truth for the hackathon.

## Current Checkpoint

**CallVault → Media Gateway is WORKING.**

Verified on a physical Android phone (OnePlus, ColorOS) over WiFi LAN.
Audio streams in real time from a phone call through WebSocket to the Node.js gateway.
The gateway chunks audio into 3-second segments and forwards them to the ML service endpoint.

## Completed

- [x] **Media Gateway** — Node.js/TypeScript server, port 8010, dual WebSocket endpoints
- [x] **Audio Chunker** — exact fixed-duration chunking with invariant verification
- [x] **Protocol Parser** — validated session.start/stop with strict type checking
- [x] **Session Manager** — isolated per-connection sessions, lifecycle management
- [x] **ML Client** — outbound WebSocket with reconnection and message queue
- [x] **Debug Recorder** — optional raw PCM capture to disk
- [x] **Dashboard** — glassmorphism live RMS visualizer at `http://localhost:8010/`
- [x] **Test Suite** — 50 Vitest tests (chunker, protocol, session)
- [x] **CallVault AIDL Extension** — `startRecording` accepts `gatewayUrl` and `sessionId`
- [x] **WebSocketAudioSink** — OkHttp push-based WebSocket client in daemon process
- [x] **DirectAudioRecorderSession Integration** — PCM streamed alongside local recording
- [x] **Settings UI** — toggle + URL input for Media Gateway in CallVault
- [x] **AppPreferences** — persistent gateway config storage
- [x] **Android APK Build** — debug APK builds and installs
- [x] **LAN Connectivity** — phone reaches laptop gateway over WiFi
- [x] **Physical Phone Test** — real call audio received and visualized

## Next

1. **Real ML Integration** — connect a deepfake detection model to `ws://localhost:8011`
2. **Verify ML receives CallVault chunks** — end-to-end from phone to inference
3. **End-to-end ML result** — gateway returns detection result to dashboard
4. **FreeSWITCH Integration** — SIP trunk with `mod_audio_stream`
5. **SIP end-to-end test** — call through FreeSWITCH, analyze with ML
6. **Final demo hardening** — error handling, UI polish, presentation

## Architecture

```
Android Phone
    ↓ phone call captured at 48 kHz mono PCM16
CallVault (privileged daemon)
    ↓ WebSocket ws://<laptop-IP>:8010
Media Gateway (Node.js, port 8010)
    ↓ 3-second chunks (288,000 bytes each)
ML Service (ws://localhost:8011)
    ↓ deepfake detection result
Dashboard (http://localhost:8010/)
```

## Key Numbers

| Parameter | Value |
|---|---|
| Sample rate | 48,000 Hz |
| Channels | 1 (mono) |
| Encoding | PCM 16-bit signed LE |
| Chunk duration | 3 seconds |
| Chunk size | 288,000 bytes |
| Gateway port | 8010 |
| ML port | 8011 |
| Test count | 50 passing |
