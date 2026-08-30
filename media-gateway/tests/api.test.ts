import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { httpServer } from '../src/server.js';
import { prisma } from '../src/persistence.js';

describe('API Endpoints', () => {
  const PORT = 8019; // Random port for tests
  const baseUrl = `http://localhost:${PORT}`;

  beforeAll(async () => {
    await new Promise<void>((resolve) => {
      httpServer.listen(PORT, '127.0.0.1', () => resolve());
    });
  });

  afterAll(async () => {
    await new Promise<void>((resolve) => {
      httpServer.close(() => resolve());
    });
    // Give time for sockets to close
    await new Promise(r => setTimeout(r, 100));
  });

  it('GET /api/stats should return stats', async () => {
    // We mock Prisma to avoid requiring a real DB for unit tests
    const spyCount = vi.spyOn(prisma.calls, 'count').mockResolvedValue(42);
    const spyAggregate = vi.spyOn(prisma.audio_streams, 'aggregate').mockResolvedValue({ _sum: { bytes_received: 1000 } } as any);
    const spyChunks = vi.spyOn(prisma.audio_chunks, 'count').mockResolvedValue(10);
    const spyRecs = vi.spyOn(prisma.recordings, 'count').mockResolvedValue(5);
    const spyRecBytes = vi.spyOn(prisma.recordings, 'aggregate').mockResolvedValue({ _sum: { size_bytes: 5000 } } as any);

    const res = await fetch(`${baseUrl}/api/stats`);
    expect(res.status).toBe(200);
    
    const data = await res.json();
    expect(data.totalCalls).toBe(42);
    expect(data.totalAudioBytes).toBe(1000);
    
    spyCount.mockRestore();
    spyAggregate.mockRestore();
    spyChunks.mockRestore();
    spyRecs.mockRestore();
    spyRecBytes.mockRestore();
  });

  it('GET /api/calls should return calls array', async () => {
    const mockCalls = [
      { id: '1', source: 'callvault' },
      { id: '2', source: 'freeswitch' }
    ];
    const spy = vi.spyOn(prisma.calls, 'findMany').mockResolvedValue(mockCalls as any);
    
    const res = await fetch(`${baseUrl}/api/calls`);
    expect(res.status).toBe(200);
    
    const calls = await res.json();
    expect(Array.isArray(calls)).toBe(true);
    expect(calls.length).toBe(2);
    expect(calls[0].id).toBe('1');
    
    spy.mockRestore();
  });

  it('GET /api/calls returns empty array on DB failure', async () => {
    const spy = vi.spyOn(prisma.calls, 'findMany').mockRejectedValue(new Error('DB Offline'));
    
    const res = await fetch(`${baseUrl}/api/calls`);
    expect(res.status).toBe(200); 
    
    const calls = await res.json();
    expect(Array.isArray(calls)).toBe(true);
    expect(calls.length).toBe(0);
    
    spy.mockRestore();
  });

  it('GET /api/calls/:id/recording returns 404 for missing recording', async () => {
    const spy = vi.spyOn(prisma.recordings, 'findFirst').mockResolvedValue(null);
    
    const res = await fetch(`${baseUrl}/api/calls/some-id/recording`);
    expect(res.status).toBe(404);
    
    spy.mockRestore();
  });
});
