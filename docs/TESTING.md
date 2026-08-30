# Testing

**Test Suite**: Vitest (vitest.config.ts)

**Running Tests**:
```bash
cd media-gateway
npm test
```

**Test Files** (50 tests total, 3 files):

### `tests/chunker.test.ts` (21 tests)
Tests the `AudioChunker` class:
- Empty push returns no chunks
- Exact chunk boundary produces one chunk
- Data smaller than chunk buffers correctly
- Data larger than chunk produces multiple chunks
- Flush returns partial chunk at session end
- Flush on empty buffer returns null
- Sequence numbers increment correctly
- Timestamps calculated correctly
- Reset clears state
- Invariant holds after push, after flush, after multiple pushes
- Various chunk sizes (16kHz, 48kHz, stereo)

Key invariant tested: `inputBytes === emittedBytes + bufferedBytes`

### `tests/protocol.test.ts` (18 tests)
Tests the protocol parser:
- Valid session.start parsed correctly
- Valid session.stop parsed correctly
- Missing fields throw ProtocolError with correct codes
- Unsupported sample rates rejected
- Unsupported channels rejected
- Unsupported encodings rejected
- Invalid JSON rejected
- Non-object messages rejected
- Unknown message types rejected

### `tests/session.test.ts` (11 tests)
Tests `SessionManager`:
- Creates session with STREAMING status
- Pushes audio and returns chunks
- Stops session → COMPLETED status
- Rejects duplicate session ID
- Duplicate stop returns null without throwing
- Remove session works
- Active count reflects live sessions
- Two concurrent sessions have isolated audio
- Session info snapshot has correct data
- stopAll cleans up everything

**Expected Results**: All 50 tests pass.

**CallVault Build Verification**:
```bash
cd CallVault
./gradlew assembleDebug
```
Expected: BUILD SUCCESSFUL

**TypeScript Type Check**:
```bash
cd media-gateway
npx tsc --noEmit
```
Expected: no errors
