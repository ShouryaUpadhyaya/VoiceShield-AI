import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import WebSocket from 'ws';
import { httpServer } from '../src/server.js';
import { prisma } from '../src/persistence.js';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import crypto from 'node:crypto';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('Synthetic Database E2E', () => {
  const PORT = 8022;
  const sessionId = `synth-test-${crypto.randomUUID()}`;

  beforeAll(async () => {
    // Note: Do NOT mock Prisma. We are testing actual DB insertion.
    await new Promise<void>((resolve) => {
      httpServer.listen(PORT, '127.0.0.1', () => resolve());
    });
  });

  afterAll(async () => {
    await new Promise<void>((resolve) => {
      httpServer.close(() => resolve());
    });
    await prisma.$disconnect();
    await new Promise(r => setTimeout(r, 100));
  });

  it('should process a call and persist to actual PostgreSQL database', async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${PORT}`);
    
    await new Promise((resolve) => ws.on('open', resolve));
    
    // 1. Start session
    ws.send(JSON.stringify({
      type: 'session.start',
      session_id: sessionId,
      source: 'synthetic-test',
      sample_rate: 48000,
      channels: 1,
      encoding: 'pcm_s16le'
    }));
    
    await new Promise(r => setTimeout(r, 100));
    
    // 2. Send 960,000 bytes (10 seconds of 48kHz mono PCM16)
    // Create a predictable pattern to verify WAV correctness
    const dummyAudio = Buffer.alloc(960000, 0x01);
    ws.send(dummyAudio);
    
    await new Promise(r => setTimeout(r, 200));
    
    // 3. Stop session
    ws.send(JSON.stringify({
      type: 'session.stop',
      session_id: sessionId
    }));
    
    await new Promise(r => setTimeout(r, 300));
    ws.close();
    
    // Wait for DB queue / file writes to flush
    await new Promise(r => setTimeout(r, 1000));
    
    // 4. Verify PostgreSQL directly
    const call = await prisma.calls.findFirst({
      where: { session_id: sessionId },
      include: {
        audio_streams: true,
        audio_chunks: true,
        recordings: true,
        connection_events: true,
      }
    });

    expect(call).toBeDefined();
    expect(call?.source).toBe('synthetic-test');
    expect(call?.audio_streams.length).toBe(1);
    expect(call?.audio_streams[0].bytes_received).toBe(960000);
    
    // Should have chunked it (3s, 3s, 3s, 1s) = 4 chunks
    expect(call?.audio_chunks.length).toBe(4);
    
    // Should have start and stop events
    expect(call?.connection_events.length).toBeGreaterThanOrEqual(2);
    
    // Should have 1 recording
    expect(call?.recordings.length).toBe(1);
    const rec = call?.recordings[0];
    expect(rec?.size_bytes).toBe(960044); // the actual audio length + 44 byte header

    // 5. Verify WAV file
    const wavPath = path.resolve(rec!.storage_path);
    expect(existsSync(wavPath)).toBe(true);

    const fileBuf = readFileSync(wavPath);
    
    // RIFF header validation
    expect(fileBuf.subarray(0, 4).toString()).toBe('RIFF');
    expect(fileBuf.subarray(8, 12).toString()).toBe('WAVE');
    expect(fileBuf.subarray(12, 16).toString()).toBe('fmt ');
    
    // Size check: RIFF header (44 bytes) + data (960,000 bytes)
    expect(fileBuf.length).toBe(960044);
    
    // 6. Verify API matches DB
    const res = await fetch(`http://127.0.0.1:${PORT}/api/calls/${call!.id}`);
    const apiCall = await res.json();
    
    expect(apiCall.session_id).toBe(sessionId);
    expect(apiCall.audio_streams[0].bytes_received).toBe(960000);
    expect(apiCall.audio_chunks.length).toBe(4);
  }, 10000); // 10s timeout
});
