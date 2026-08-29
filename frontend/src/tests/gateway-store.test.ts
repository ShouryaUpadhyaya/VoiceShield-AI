import { describe, it, expect, beforeEach } from 'vitest';
import { useGatewayStore } from '../stores/gateway-store';

describe('Gateway Store', () => {
  beforeEach(() => {
    const store = useGatewayStore.getState();
    // Reset state before each test
    useGatewayStore.setState({
      status: 'OFFLINE',
      network: null,
      sessions: {},
      chunks: {}
    });
  });

  it('should set status', () => {
    useGatewayStore.getState().setStatus('ONLINE');
    expect(useGatewayStore.getState().status).toBe('ONLINE');
  });

  it('should set network', () => {
    const network = { recommendedIp: '192.168.1.5', interfaces: [], port: 8010 };
    useGatewayStore.getState().setNetwork(network);
    expect(useGatewayStore.getState().network).toEqual(network);
  });

  it('should update session and implicitly create it if it does not exist', () => {
    const sessionId = 'test-session-1';
    
    useGatewayStore.getState().updateSession(sessionId, {
      rms: 100,
      bytes: 1024,
      status: 'STREAMING'
    });

    const session = useGatewayStore.getState().sessions[sessionId];
    expect(session).toBeDefined();
    expect(session.sessionId).toBe(sessionId);
    expect(session.rms).toBe(100);
    expect(session.bytes).toBe(1024);
    expect(session.status).toBe('STREAMING');
  });

  it('should add chunks and keep a maximum of 20 chunks', () => {
    const sessionId = 'test-session-1';
    
    // Add 25 chunks
    for (let i = 1; i <= 25; i++) {
      useGatewayStore.getState().addChunk(sessionId, {
        sequence: i,
        bytes: 96000,
        durationMs: 3000,
        timestampMs: Date.now(),
        mlStatus: 'SENT'
      });
    }

    const chunks = useGatewayStore.getState().chunks[sessionId];
    expect(chunks.length).toBe(20);
    expect(chunks[0].sequence).toBe(6); // 25 - 20 = 5, so first is 6
    expect(chunks[19].sequence).toBe(25);
  });

  it('should deduplicate chunks based on sequence', () => {
    const sessionId = 'test-session-1';
    
    const chunk = {
      sequence: 1,
      bytes: 96000,
      durationMs: 3000,
      timestampMs: Date.now(),
      mlStatus: 'SENT' as const
    };

    useGatewayStore.getState().addChunk(sessionId, chunk);
    useGatewayStore.getState().addChunk(sessionId, chunk);

    const chunks = useGatewayStore.getState().chunks[sessionId];
    expect(chunks.length).toBe(1);
  });

  it('should remove session and chunks', () => {
    const sessionId = 'test-session-1';
    useGatewayStore.getState().updateSession(sessionId, { status: 'STREAMING' });
    useGatewayStore.getState().addChunk(sessionId, {
      sequence: 1, bytes: 96000, durationMs: 3000, timestampMs: Date.now(), mlStatus: 'SENT'
    });

    expect(useGatewayStore.getState().sessions[sessionId]).toBeDefined();
    expect(useGatewayStore.getState().chunks[sessionId]).toBeDefined();

    useGatewayStore.getState().removeSession(sessionId);

    expect(useGatewayStore.getState().sessions[sessionId]).toBeUndefined();
    expect(useGatewayStore.getState().chunks[sessionId]).toBeUndefined();
  });
});
