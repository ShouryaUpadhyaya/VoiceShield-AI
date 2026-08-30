# Database Configuration

The VoiceShield-AI media gateway uses PostgreSQL for persistence.

## Development Setup

To avoid conflicts with any existing local PostgreSQL installations, the development Docker Compose setup maps the container to host port **15432**.

### Start Database
```bash
cd media-gateway
docker compose up -d postgres
```

### Apply Schema
```bash
npx prisma db push
```

## Schema Overview

- **calls**: Tracks active and completed calls.
- **audio_streams**: Tracks audio formats and bytes received per call.
- **audio_chunks**: Tracks individual chunk timestamps and sequence metrics.
- **recordings**: Stores paths and metadata to saved WAV files.
- **connection_events**: Stores WebSocket lifecycle events.

## Troubleshooting

If you encounter `PrismaClientInitializationError` indicating authentication failed, ensure your `DATABASE_URL` in `.env` is set correctly:

```
DATABASE_URL="postgresql://postgres:voiceshield@localhost:15432/voiceshield"
```
