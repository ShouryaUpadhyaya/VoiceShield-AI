# Media Gateway

The Media Gateway acts as the central router and standardizer of audio data in VoiceShield-AI. 

## Key Responsibilities
1. **Ingestion**: Accepts WebSocket connections from CallVault and FreeSWITCH.
2. **Standardization**: Buffers incoming PCM bytes into exactly 3-second chunks (invariant logic).
3. **Distribution**: Forwards complete chunks to the ML Service.
4. **Persistence**: Saves entire calls as `.wav` files and logs metadata to PostgreSQL asynchronously.
5. **Observability**: Hosts a Dashboard at `http://localhost:8010/` to visualize the pipeline in real-time.

## Key Modules
- `server.ts`: HTTP + WebSocket ingress.
- `chunker.ts`: The state machine responsible for accurate 3-second buffering.
- `session.ts`: Manages session lifecycles and strictly isolates audio between different calls.
- `persistence.ts`: Non-blocking database write queue.
- `api.ts`: Exposes REST endpoints for querying historical calls and downloading recordings.
