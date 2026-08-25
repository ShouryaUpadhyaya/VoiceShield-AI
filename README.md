# VoiceShield-AI

Real-time voice deepfake detection for live phone calls. Captures call audio from
Android phones, streams it through a media gateway, and analyzes it with ML models
for deepfake detection.

## Current Status

| Feature | Status |
|---|---|
| Media Gateway | ✅ Working |
| 3-second PCM chunking | ✅ Working |
| Synthetic audio tests | ✅ 50 tests passing |
| Fake ML integration | ✅ Working |
| CallVault WebSocket integration | ✅ Working |
| Physical Android test | ✅ Verified on device |
| Real ML integration | ⬜ Next |
| FreeSWITCH integration | ⬜ Planned |
| SIP end-to-end test | ⬜ Planned |

## Quick Start

### 1. Start the Media Gateway

```bash
cd media-gateway
npm install
npm run dev
```

Gateway starts on `http://0.0.0.0:8010`. Dashboard at `http://localhost:8010/`.

### 2. Configure CallVault on Android

1. Build and install the APK (see [docs/CALLVAULT.md](docs/CALLVAULT.md))
2. Open CallVault → Settings → Enable "Media Gateway"
3. Set WebSocket URL to `ws://<your-laptop-LAN-IP>:8010`
4. Make a phone call — audio streams to the gateway in real time

### 3. Run Tests

```bash
cd media-gateway
npm test          # 50 tests (chunker, protocol, session)
npx tsc --noEmit  # Type check
```

## Architecture

```
Android CallVault ──WebSocket PCM──▶ Media Gateway ──3-sec chunks──▶ ML Service
                                          ▲
FreeSWITCH (planned) ──WebSocket PCM──────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full architecture.

## Project Layout

```
CallVault/          Android call recording app (separate git repo)
media-gateway/      Node.js/TypeScript audio ingestion gateway
  src/              Gateway source (server, chunker, protocol, session, ML client)
  tests/            Vitest test suite (50 tests)
  public/           Dashboard HTML
ml/                 Deepfake detection model (WavLM + LFCC/MGD fusion)
backend/            FastAPI service
frontend/           React + Vite UI
docs/               Project documentation
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — system design and data flow
- [CallVault Setup](docs/CALLVAULT.md) — Android app build, install, configure
- [Media Gateway](docs/MEDIA_GATEWAY.md) — gateway internals, endpoints, config
- [Protocol](docs/PROTOCOL.md) — WebSocket protocol specification
- [Testing](docs/TESTING.md) — test suite and verification
- [Troubleshooting](docs/TROUBLESHOOTING.md) — common issues and fixes
