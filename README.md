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

## Development Setup

### 1. Start PostgreSQL

```bash
cd media-gateway
docker compose up -d postgres
```

### 2. Verify PostgreSQL

```bash
docker compose ps
```

### 3. Apply Prisma schema

```bash
npx prisma db push
```

### 4. Start Media Gateway

```bash
npm run dev
```

Gateway:
http://localhost:8010

### 5. Start Next.js

```bash
cd ../frontend
npm install
npm run dev
```

Frontend:
http://localhost:3000

### 6. Android

Use the LAN IP displayed by the dashboard:

```
ws://<LAPTOP-LAN-IP>:8010
```

## Troubleshooting

### Docker unavailable

```bash
docker info
```
If Docker daemon is not running, start Docker before: `docker compose up -d postgres`

### Port 5432 occupied

```bash
ss -ltnp | grep 5432
```
Do not kill unrelated PostgreSQL processes automatically.

### Port 8010 occupied

```bash
lsof -i :8010
```
If the existing Media Gateway is running, do not start another copy.

### Database authentication error

Verify:
```
DATABASE_URL
```
matches:
```
postgresql://postgres:voiceshield@localhost:15432/voiceshield
```
for the Docker configuration.

### Frontend cannot connect

Verify:
Media Gateway: `http://localhost:8010`
Frontend: `http://localhost:3000`
`NEXT_PUBLIC_GATEWAY_URL` is set to `http://localhost:8010` in `frontend/.env.local`

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
