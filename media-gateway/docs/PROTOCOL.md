# Protocol Definition

The Media Gateway uses two distinct WebSocket protocols.

## Ingress (Source -> Gateway)

**1. Session Start (JSON string)**
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

**2. Audio Data (Binary)**
Raw PCM audio bytes. Size is arbitrary.

**3. Session Stop (JSON string)**
```json
{
  "type": "session.stop",
  "session_id": "uuid"
}
```

## Egress (Gateway -> ML Service)

For every complete 3-second chunk, the gateway emits:

**1. Chunk Metadata (JSON string)**
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

**2. Audio Data (Binary)**
The exact bytes corresponding to the chunk (e.g. 96,000 bytes).
