import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { io } from 'socket.io-client';
import WebSocket from 'ws';
import { httpServer, sessionManager } from '../src/server.js';
import { prisma } from '../src/persistence.js';
import { getRecommendedLanIp } from '../src/network.js';

describe('LAN Connection End-to-End', () => {
  const PORT = 8025;
  const lanIp = getRecommendedLanIp();
  
  beforeAll(async () => {
    // Bind specifically to 0.0.0.0 to accept LAN connections
    await new Promise<void>((resolve) => {
      httpServer.listen(PORT, '0.0.0.0', () => resolve());
    });
  });

  afterAll(async () => {
    await new Promise<void>((resolve) => {
      httpServer.close(() => resolve());
    });
    await new Promise(r => setTimeout(r, 100)); // allow sockets to clean up
  });

  it('should allow audio ingestion and broadcast stats over the LAN IP interface', async () => {
    // We are simulating a "different device" by explicitly connecting 
    // to the external LAN IP address instead of 127.0.0.1
    const audioSocket = new WebSocket(`ws://${lanIp}:${PORT}`);
    const dashboardSocket = io(`http://${lanIp}:${PORT}/dashboard`, { transports: ['websocket'] });
    
    // Mocks for DB
    const spyCallsCreate = vi.spyOn(prisma.calls, 'create').mockResolvedValue({} as any);
    const spyCallsUpdate = vi.spyOn(prisma.calls, 'update').mockResolvedValue({} as any);
    const spyStreamsCreate = vi.spyOn(prisma.audio_streams, 'create').mockResolvedValue({} as any);
    const spyStreamsUpdate = vi.spyOn(prisma.audio_streams, 'update').mockResolvedValue({} as any);
    const spyStreamsFindFirst = vi.spyOn(prisma.audio_streams, 'findFirst').mockResolvedValue({ id: 'dummy' } as any);
    const spyEventsCreate = vi.spyOn(prisma.connection_events, 'create').mockResolvedValue({} as any);
    const spyRecsCreate = vi.spyOn(prisma.recordings, 'create').mockResolvedValue({} as any);
    const spyChunksCreate = vi.spyOn(prisma.audio_chunks, 'create').mockResolvedValue({} as any);
    
    // Connect both sockets
    await Promise.all([
      new Promise((resolve) => audioSocket.on('open', resolve)),
      new Promise((resolve) => dashboardSocket.on('connect', resolve))
    ]);

    const sessionId = 'lan-remote-session-1';
    
    // Track if dashboard receives the stats for this session
    let receivedStats = false;
    dashboardSocket.on('stats', (msg) => {
      if (msg.session_id === sessionId) {
        receivedStats = true;
      }
    });

    // 1. Start session from remote audio client
    audioSocket.send(JSON.stringify({
      type: 'session.start',
      session_id: sessionId,
      source: 'test-remote-device',
      sample_rate: 48000,
      channels: 1,
      encoding: 'pcm_s16le'
    }));
    
    await new Promise(r => setTimeout(r, 50));
    
    // 2. Send some audio data
    const dummyAudio = Buffer.alloc(960000, 0x01);
    audioSocket.send(dummyAudio);
    
    await new Promise(r => setTimeout(r, 100));
    
    audioSocket.send(JSON.stringify({
      type: 'session.stop',
      session_id: sessionId
    }));
    
    await new Promise(r => setTimeout(r, 200));
    
    audioSocket.close();
    dashboardSocket.disconnect();
    
    // Verify that the dashboard received the broadcasted event
    expect(receivedStats).toBe(true);
    
    // Ensure the session was actually processed by checking internal state/mocks
    expect(spyCallsCreate).toHaveBeenCalled();
    expect(spyChunksCreate).toHaveBeenCalled();
    
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
