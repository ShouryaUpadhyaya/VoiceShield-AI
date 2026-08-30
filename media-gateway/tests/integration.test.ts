import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import WebSocket from 'ws';
import { httpServer } from '../src/server.js';
import { prisma } from '../src/persistence.js';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('Integration End-to-End', () => {
  const PORT = 8021;
  
  beforeAll(async () => {
    await new Promise<void>((resolve) => {
      httpServer.listen(PORT, '127.0.0.1', () => resolve());
    });
  });

  afterAll(async () => {
    await new Promise<void>((resolve) => {
      httpServer.close(() => resolve());
    });
    await new Promise(r => setTimeout(r, 100));
  });

  it('should process a full call lifecycle correctly without crashing', async () => {
    const socket = new WebSocket(`ws://127.0.0.1:${PORT}`);
    
    // Mocks for DB so we don't need a real Postgres instance for tests
    const spyCallsCreate = vi.spyOn(prisma.calls, 'create').mockResolvedValue({} as any);
    const spyCallsUpdate = vi.spyOn(prisma.calls, 'update').mockResolvedValue({} as any);
    const spyStreamsCreate = vi.spyOn(prisma.audio_streams, 'create').mockResolvedValue({} as any);
    const spyStreamsUpdate = vi.spyOn(prisma.audio_streams, 'update').mockResolvedValue({} as any);
    const spyStreamsFindFirst = vi.spyOn(prisma.audio_streams, 'findFirst').mockResolvedValue({ id: 'dummy' } as any);
    const spyEventsCreate = vi.spyOn(prisma.connection_events, 'create').mockResolvedValue({} as any);
    const spyRecsCreate = vi.spyOn(prisma.recordings, 'create').mockResolvedValue({} as any);
    const spyChunksCreate = vi.spyOn(prisma.audio_chunks, 'create').mockResolvedValue({} as any);
    
    await new Promise((resolve) => socket.on('open', resolve));
    
    const sessionId = 'integration-session-1';
    
    // 1. Start session
    socket.send(JSON.stringify({
      type: 'session.start',
      session_id: sessionId,
      source: 'test',
      sample_rate: 48000,
      channels: 1,
      encoding: 'pcm_s16le'
    }));
    
    await new Promise(r => setTimeout(r, 50));
    
    // 2. Send 10s of audio = 960,000 bytes
    const dummyAudio = Buffer.alloc(960000, 0x01);
    socket.send(dummyAudio);
    
    await new Promise(r => setTimeout(r, 100));
    
    // 3. Stop session
    socket.send(JSON.stringify({
      type: 'session.stop',
      session_id: sessionId
    }));
    
    await new Promise(r => setTimeout(r, 200));
    
    socket.close();
    
    // Wait for file writes and DB queue to process completely
    await new Promise(r => setTimeout(r, 200));
    
    // Verify DB was updated asynchronously (queue processed)
    expect(spyCallsCreate).toHaveBeenCalled();
    expect(spyStreamsCreate).toHaveBeenCalled();
    expect(spyEventsCreate).toHaveBeenCalledTimes(2); // Start and Stop
    
    // 3 full chunks (3s each = 9s) + 1 partial chunk (1s) = 4 chunks
    expect(spyChunksCreate).toHaveBeenCalledTimes(4);
    
    expect(spyCallsUpdate).toHaveBeenCalled();
    expect(spyStreamsUpdate).toHaveBeenCalled();
    expect(spyRecsCreate).toHaveBeenCalled();
    
    // Verify WAV was written to disk
    const wavPath = path.join(__dirname, '..', 'data', 'calls', `${sessionId}.wav`);
    expect(existsSync(wavPath)).toBe(true);
    
    // Clean up
    spyCallsCreate.mockRestore();
    spyCallsUpdate.mockRestore();
    spyStreamsCreate.mockRestore();
    spyStreamsUpdate.mockRestore();
    spyStreamsFindFirst.mockRestore();
    spyEventsCreate.mockRestore();
    spyRecsCreate.mockRestore();
    spyChunksCreate.mockRestore();
  });
});
