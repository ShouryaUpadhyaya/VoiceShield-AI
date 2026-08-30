/**
 * Fake ML WebSocket Server
 *
 * Accepts connections from the gateway and logs chunk metadata.
 * Proves the gateway pipeline independently of the real ML implementation.
 *
 * Usage:
 *   tsx scripts/fake-ml-server.ts
 *   tsx scripts/fake-ml-server.ts --port 8011
 */

import { WebSocketServer, WebSocket } from 'ws';

// ── Parse CLI args ─────────────────────────────────────────────────

const port = parseInt(
  process.argv.find((_, i) => process.argv[i - 1] === '--port') ?? '8011',
  10,
);

// ── Server ─────────────────────────────────────────────────────────

const wss = new WebSocketServer({ port });

function log(msg: string): void {
  console.log(`[ML-FAKE] ${msg}`);
}

log(`Server listening on ws://localhost:${port}`);

wss.on('connection', (ws: WebSocket) => {
  log('Client connected');

  // State machine: alternate between JSON metadata and binary payload
  let pendingMetadata: {
    session_id: string;
    sequence: number;
    bytes: number;
    duration_ms: number;
    sample_rate: number;
    channels: number;
  } | null = null;

  const sessionChunks = new Map<string, number>();
  let lastSessionId: string | null = null;

  ws.on('message', (data: Buffer, isBinary: boolean) => {
    if (!isBinary) {
      // JSON metadata frame
      try {
        const msg = JSON.parse(data.toString());
        if (msg.type === 'audio.chunk') {
          pendingMetadata = msg;
          const sid = msg.session_id;

          if (sid !== lastSessionId) {
            log(`SESSION ${sid}`);
            lastSessionId = sid;
          }

          if (!sessionChunks.has(sid)) {
            sessionChunks.set(sid, 0);
          }
        } else {
          log(`UNKNOWN MESSAGE: ${JSON.stringify(msg)}`);
        }
      } catch {
        log(`INVALID JSON: ${data.toString().substring(0, 100)}`);
      }
    } else {
      // Binary PCM payload
      if (pendingMetadata) {
        const m = pendingMetadata;
        const count = (sessionChunks.get(m.session_id) ?? 0) + 1;
        sessionChunks.set(m.session_id, count);

        log(
          `CHUNK seq=${m.sequence} bytes=${data.length} duration=${m.duration_ms}ms rate=${m.sample_rate} ch=${m.channels}`,
        );

        if (data.length !== m.bytes) {
          log(`  ⚠️ SIZE MISMATCH: metadata says ${m.bytes}, got ${data.length}`);
        }

        // Send a simple acknowledgement back to the gateway
        ws.send(
          JSON.stringify({
            type: 'audio.chunk.ack',
            session_id: m.session_id,
            sequence: m.sequence,
            received_bytes: data.length,
          }),
        );

        pendingMetadata = null;
      } else {
        log(`UNEXPECTED BINARY: ${data.length} bytes (no pending metadata)`);
      }
    }
  });

  ws.on('close', () => {
    for (const [sid, count] of sessionChunks.entries()) {
      log(`Client disconnected — ${count} chunks received for session ${sid}`);
    }
  });

  ws.on('error', (err) => {
    log(`ERROR: ${err.message}`);
  });
});

// ── Graceful shutdown ──────────────────────────────────────────────

process.on('SIGINT', () => {
  log('Shutting down...');
  wss.close();
  process.exit(0);
});
