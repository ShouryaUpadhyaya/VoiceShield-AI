# Media Gateway — Hackathon MVP

Real-time call-audio media gateway that receives audio from multiple sources (CallVault Android, FreeSWITCH), buffers it into exact 3-second PCM chunks, and forwards them to an ML service over WebSocket.

## Architecture

```
                         ┌──────────────────┐
                         │    ML SERVICE     │
                         │  teammate service │
                         └────────▲──────────┘
                                  │
                            WebSocket
                          (JSON + binary)
                                  │
                         ┌────────┴──────────┐       ┌─────────────────┐
                         │   MEDIA GATEWAY   ├──────►│   POSTGRESQL    │
                         │  Node + TypeScript │       │  Call Metadata  │
                         │    port 8010       │       └─────────────────┘
                         └────────▲──────────┘
                                  │
                            WebSocket
                          (protocol + PCM)
                                  │
                    ┌─────────────┼─────────────┐
                    │             │              │
               CallVault    FreeSWITCH     Synthetic
               Android     mod_audio_stream   Test
```

## Quick Start

```bash
# Install
npm install

# Run tests (50 tests across chunker, protocol, session)
npm test

# Setup PostgreSQL Database
docker compose up -d postgres
npx prisma db push

# Start the gateway
npm run dev

# Open the dashboard
http://localhost:8010/

# In another terminal, start the fake ML server
npm run fake-ml

# In another terminal, send test audio (10 seconds)
npm run send-test -- --duration 10

# Send 30 seconds (expect exactly 10 chunks)
npm run send-test -- --duration 30
```

## Health Endpoint

```bash
curl http://localhost:8010/health
```

```json
{
  "status": "ok",
  "mlConnected": true,
  "activeSessions": 0,
  "sessions": [],
  "uptime": 42.5
}
```

## Source → Gateway Protocol

### 1. Session Start (JSON)
```json
{
  "type": "session.start",
  "session_id": "uuid",
  "source": "callvault",
  "sample_rate": 16000,
  "channels": 1,
  "encoding": "pcm_s16le"
}
```

### 2. Audio Data (Binary WebSocket Frames)
Raw PCM audio in any frame size.

### 3. Session Stop (JSON)
```json
{
  "type": "session.stop",
  "session_id": "uuid"
}
```

## Gateway → ML Protocol

For each complete 3-second chunk:

```json
{
  "type": "audio.chunk",
  "session_id": "uuid",
  "sequence": 0,
  "timestamp_ms": 0,
  "duration_ms": 3000,
  "sample_rate": 16000,
  "channels": 1,
  "encoding": "pcm_s16le",
  "bytes": 96000
}
```

Followed by the binary PCM payload.

## Audio Contract

| Parameter | Value |
|-----------|-------|
| Encoding | PCM signed 16-bit little endian |
| Chunk duration | 3 seconds |
| Chunk size | Calculated: `sampleRate × channels × 2 × 3` |

Supported sample rates: 8000, 16000, 44100, 48000 Hz.

### Example: 16 kHz Mono
```
16,000 × 1 × 2 × 3 = 96,000 bytes per chunk
```

### Example: 48 kHz Mono (CallVault native)
```
48,000 × 1 × 2 × 3 = 288,000 bytes per chunk
```

## Configuration

Copy `.env.example` to `.env`:

```env
PORT=8010
HOST=0.0.0.0
ML_WS_URL=ws://localhost:8011
CHUNK_DURATION_SEC=3
SAVE_DEBUG_AUDIO=false
DEBUG_AUDIO_DIR=./debug-recordings
DATABASE_URL=postgresql://postgres:password@localhost:5432/voiceshield
LOG_LEVEL=info
```

## Project Structure

```
media-gateway/
├── src/
│   ├── server.ts          # HTTP + WS server, health endpoint
│   ├── config.ts          # Env-based configuration
│   ├── protocol.ts        # Session protocol parser + validation
│   ├── session.ts         # Session manager (isolation, lifecycle)
│   ├── chunker.ts         # 3-second audio chunker (CRITICAL)
│   ├── ml-client.ts       # Outbound WebSocket to ML service
│   ├── logger.ts          # Structured logging
│   └── debug-recorder.ts  # Optional raw PCM debug dump
├── tests/
│   ├── chunker.test.ts    # 21 tests — boundary, invariant, data integrity
│   ├── protocol.test.ts   # 18 tests — validation, error codes
│   └── session.test.ts    # 11 tests — lifecycle, isolation
├── scripts/
│   ├── send-test-audio.ts # Synthetic 1kHz sine → gateway
│   └── fake-ml-server.ts  # Mock ML that logs chunks
├── .env.example
├── package.json
├── tsconfig.json
├── vitest.config.ts
└── Dockerfile
```

## Key Invariants

1. **Chunk accounting**: `totalInputBytes === totalEmittedBytes + bufferedBytes` — no audio silently duplicated or lost
2. **Session isolation**: Audio from session A never reaches session B
3. **Fault tolerance**: A failure in one external service does not crash the gateway
