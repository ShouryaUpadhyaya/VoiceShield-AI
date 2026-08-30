# Media Gateway

**Purpose**: Receives real-time PCM audio from Android phones (CallVault) and SIP gateways (FreeSWITCH, future), buffers it into fixed-duration chunks, and forwards those chunks to the ML deepfake detection service.

**Ports**: 8010 (default, configurable via `PORT` env)

**HTTP Endpoints**:
- `GET /health` — JSON health check with active session info
- `GET /` — serves the dashboard HTML

**WebSocket Endpoints**:
- `ws://host:8010/` — audio source ingestion (CallVault, FreeSWITCH)
- `ws://host:8010/dashboard` — browser dashboard (receives real-time stats)

**Source Protocol** (Source → Gateway):
1. JSON `session.start` — declares audio format
2. Binary WebSocket frames — raw PCM audio
3. JSON `session.stop` — ends session

**Session Management**: `SessionManager` creates/tracks sessions. Each session gets an `AudioChunker`. Sessions are identified by `session_id`. Duplicate session IDs are rejected.

**Chunking**: `AudioChunker` buffers arbitrary-size WebSocket frames and produces exact fixed-duration chunks. Default chunk duration: 3 seconds. Chunk size is dynamically calculated from the audio format:

```
chunkBytes = sampleRate × channels × bytesPerSample × durationSec
```

For 48 kHz mono PCM16: `48000 × 1 × 2 × 3 = 288,000 bytes/chunk`
For 16 kHz mono PCM16: `16000 × 1 × 2 × 3 = 96,000 bytes/chunk`

Chunk size is NEVER hardcoded.

**ML Protocol** (Gateway → ML):
1. JSON metadata with `type: 'audio.chunk'`, session_id, sequence, timestampMs, durationMs, sampleRate, channels, encoding
2. Binary payload (the PCM chunk)

**Environment Variables** (from `.env.example`):
- `PORT` (default: 8010)
- `HOST` (default: 0.0.0.0)
- `ML_WS_URL` (default: ws://localhost:8011)
- `CHUNK_DURATION_SEC` (default: 3)
- `SAVE_DEBUG_AUDIO` (default: false)
- `DEBUG_AUDIO_DIR` (default: ./debug-recordings)
- `LOG_LEVEL` (default: info)

**Debug Recording**: When `SAVE_DEBUG_AUDIO=true`, raw PCM is saved to `DEBUG_AUDIO_DIR/<session_id>.raw`. Can be played with: `aplay -f S16_LE -r 48000 -c 1 <file>.raw`
