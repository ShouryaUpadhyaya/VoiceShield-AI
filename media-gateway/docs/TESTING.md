# Testing

The Media Gateway features a suite of 50 tests via Vitest.

```bash
npm test
```

## Key Test Suites
- **chunker.test.ts**: Verifies the strict byte-counting logic and invariants (e.g., `totalEmitted = received - buffered`).
- **protocol.test.ts**: Verifies WebSocket message validation and error handling for malformed packets.
- **session.test.ts**: Ensures strict isolation between multiple concurrent calls, verifying that audio data never cross-contaminates.
