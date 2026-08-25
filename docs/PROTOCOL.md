# Protocol

### Source → Gateway Protocol

**1. session.start** (JSON text frame)

Required fields:
- `type`: `"session.start"` (string, required)
- `session_id`: unique session identifier (string, required, non-empty)
- `source`: source name, e.g. `"CallVault"` or `"FreeSWITCH"` (string, required, non-empty)
- `sample_rate`: sample rate in Hz (number, required, one of: 8000, 16000, 44100, 48000)
- `channels`: channel count (number, required, one of: 1, 2)
- `encoding`: audio encoding (string, required, one of: `"pcm_s16le"`)

Example:
```json
{
  "type": "session.start",
  "session_id": "session_1724623456789",
  "source": "CallVault",
  "sample_rate": 48000,
  "channels": 1,
  "encoding": "pcm_s16le"
}
```

**2. Binary PCM frames** (binary WebSocket frames)

Raw PCM audio bytes. Arbitrary size. The gateway buffers and chunks them.

**3. session.stop** (JSON text frame)

Required fields:
- `type`: `"session.stop"` (string, required)
- `session_id`: must match the session.start session_id (string, required, non-empty)

Example:
```json
{
  "type": "session.stop",
  "session_id": "session_1724623456789"
}
```

### Gateway → ML Protocol

**1. audio.chunk metadata** (JSON text frame)

Fields:
- `type`: `"audio.chunk"` (string)
- `session_id`: session identifier (string)
- `sequence`: 0-based chunk sequence number (number)
- `timestamp_ms`: timestamp in ms from session start (number)
- `duration_ms`: chunk duration in ms (number, 3000 for full chunks)
- `sample_rate`: sample rate (number)
- `channels`: channel count (number)
- `encoding`: encoding (string)

Example:
```json
{
  "type": "audio.chunk",
  "session_id": "session_1724623456789",
  "sequence": 0,
  "timestamp_ms": 0,
  "duration_ms": 3000,
  "sample_rate": 48000,
  "channels": 1,
  "encoding": "pcm_s16le"
}
```

**2. Binary payload** (binary WebSocket frame)

The PCM chunk. For 48 kHz mono PCM16 at 3 seconds = 288,000 bytes. Partial final chunks may be smaller.

### Error Behavior

- Invalid JSON → `ProtocolError` code `INVALID_JSON`
- Missing `type` → code `MISSING_TYPE`
- Unknown type → code `UNKNOWN_TYPE`
- Missing `session_id` → code `MISSING_SESSION_ID`
- Unsupported sample rate → code `UNSUPPORTED_SAMPLE_RATE`
- Duplicate session ID → rejected
- Binary data without active session → ignored with warning
