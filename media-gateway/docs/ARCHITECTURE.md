# VoiceShield-AI Architecture

VoiceShield-AI is a real-time call monitoring and fraud detection system. The primary components are:

1. **CallVault**: An Android application that runs in the background and intercepts phone call audio in real-time.
2. **Media Gateway**: A Node.js/TypeScript WebSocket server that receives raw PCM audio, chunks it into precise 3-second segments, saves it for persistence, and forwards it to the ML service.
3. **ML Service (Dhwani)**: An external Python service that runs voice biometric and fraud detection models on the incoming 3-second chunks.
4. **PostgreSQL**: A relational database to store call metadata, chunk references, and analysis results for historical querying.

## Data Flow
- Android `CallVault` establishes a WebSocket connection with the `Media Gateway`.
- Raw audio (usually 48kHz PCM) streams in real-time to the Gateway.
- The `Chunker` buffers exactly 3.0s worth of audio.
- When 3 seconds are reached, the chunk is emitted to the `ML Service` via an outbound WebSocket.
- Meanwhile, the Gateway records the call directly to disk as a `.wav` file, and uses an asynchronous write queue to update `PostgreSQL` without blocking the main event loop.
