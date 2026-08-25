# Database schema

The Media Gateway uses PostgreSQL via Prisma.

## Async Persistence
The audio path is extremely latency-sensitive. A dedicated async queue in `src/persistence.ts` ensures that slow database queries or connection timeouts *never* block the Node.js event loop or cause audio stutters.

## Schema
- `calls`: Core call record, session ID, source, status.
- `audio_streams`: Audio configuration (sample rate, channels, total bytes).
- `audio_chunks`: Metadata for each 3-second chunk sent to ML.
- `recordings`: Disk storage locations for final `.wav` files.
- `connection_events`: Detailed logs of connection and disconnection.
- `ml_results`: Future extension to store inferences from the ML service.
