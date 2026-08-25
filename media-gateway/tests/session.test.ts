/**
 * Session Manager Tests
 *
 * Tests session lifecycle, multi-session isolation, and cleanup.
 */

import { describe, it, expect } from 'vitest';
import { AudioSession, SessionManager } from '../src/session.js';
import type { SessionStartMessage } from '../src/protocol.js';

const CHUNK_DUR = 3;

function startMsg(id: string, source = 'test'): SessionStartMessage {
  return {
    type: 'session.start',
    session_id: id,
    source,
    sample_rate: 16000,
    channels: 1,
    encoding: 'pcm_s16le',
  };
}

describe('SessionManager', () => {
  it('creates a session with STREAMING status', () => {
    const mgr = new SessionManager(CHUNK_DUR);
    const session = mgr.createSession(startMsg('s1'));
    expect(session.status).toBe('STREAMING');
    expect(session.sessionId).toBe('s1');
    expect(session.source).toBe('test');
  });

  it('pushes audio and returns chunks', () => {
    const mgr = new SessionManager(CHUNK_DUR);
    const session = mgr.createSession(startMsg('s1'));
    const chunks = session.pushAudio(Buffer.alloc(96000));
    expect(chunks).toHaveLength(1);
    expect(chunks[0].sequence).toBe(0);
    expect(chunks[0].data.length).toBe(96000);
  });

  it('stops session → COMPLETED status', () => {
    const mgr = new SessionManager(CHUNK_DUR);
    const session = mgr.createSession(startMsg('s1'));
    session.pushAudio(Buffer.alloc(50000));
    const partial = session.stop();
    expect(session.status).toBe('COMPLETED');
    expect(partial).not.toBeNull();
    expect(partial!.data.length).toBe(50000);
  });

  it('rejects duplicate session ID', () => {
    const mgr = new SessionManager(CHUNK_DUR);
    mgr.createSession(startMsg('s1'));
    expect(() => mgr.createSession(startMsg('s1'))).toThrow('Session already exists');
  });

  it('duplicate stop returns null without throwing', () => {
    const mgr = new SessionManager(CHUNK_DUR);
    const session = mgr.createSession(startMsg('s1'));
    session.stop();
    expect(session.status).toBe('COMPLETED');
    const result = session.stop();
    expect(result).toBeNull(); // No error, just null
  });

  it('remove session → getSession returns undefined', () => {
    const mgr = new SessionManager(CHUNK_DUR);
    mgr.createSession(startMsg('s1'));
    mgr.removeSession('s1');
    expect(mgr.getSession('s1')).toBeUndefined();
  });

  it('activeCount reflects live sessions', () => {
    const mgr = new SessionManager(CHUNK_DUR);
    expect(mgr.activeCount).toBe(0);

    const s1 = mgr.createSession(startMsg('s1'));
    expect(mgr.activeCount).toBe(1);

    mgr.createSession(startMsg('s2'));
    expect(mgr.activeCount).toBe(2);

    s1.stop();
    expect(mgr.activeCount).toBe(1);
  });

  it('two concurrent sessions → audio is ISOLATED', () => {
    const mgr = new SessionManager(CHUNK_DUR);
    const sessionA = mgr.createSession(startMsg('A', 'callvault'));
    const sessionB = mgr.createSession(startMsg('B', 'freeswitch'));

    // Push 96000 bytes to A (= 1 chunk)
    const chunksA = sessionA.pushAudio(Buffer.alloc(96000, 0xAA));
    expect(chunksA).toHaveLength(1);
    expect(chunksA[0].data[0]).toBe(0xAA);

    // B should have ZERO chunks and ZERO bytes received
    expect(sessionB.totalBytesReceived).toBe(0);
    expect(sessionB.chunker.currentSequence).toBe(0);
    expect(sessionB.chunker.bufferedBytes).toBe(0);

    // Push to B separately
    const chunksB = sessionB.pushAudio(Buffer.alloc(96000, 0xBB));
    expect(chunksB).toHaveLength(1);
    expect(chunksB[0].data[0]).toBe(0xBB);

    // Verify A's data was not contaminated
    expect(sessionA.chunker.currentSequence).toBe(1); // Still 1, not 2
    expect(chunksA[0].data[0]).toBe(0xAA);
    expect(chunksB[0].data[0]).toBe(0xBB);
  });

  it('session info snapshot has correct data', () => {
    const mgr = new SessionManager(CHUNK_DUR);
    const session = mgr.createSession(startMsg('s1', 'callvault'));
    session.pushAudio(Buffer.alloc(50000));
    const info = session.toInfo();
    expect(info.sessionId).toBe('s1');
    expect(info.source).toBe('callvault');
    expect(info.format.sampleRate).toBe(16000);
    expect(info.format.channels).toBe(1);
    expect(info.format.encoding).toBe('pcm_s16le');
    expect(info.status).toBe('STREAMING');
    expect(info.totalBytesReceived).toBe(50000);
    expect(info.bufferedBytes).toBe(50000);
    expect(info.chunkSequence).toBe(0);
  });

  it('unknown session → getSession returns undefined', () => {
    const mgr = new SessionManager(CHUNK_DUR);
    expect(mgr.getSession('nonexistent')).toBeUndefined();
  });

  it('stopAll cleans up everything', () => {
    const mgr = new SessionManager(CHUNK_DUR);
    mgr.createSession(startMsg('s1'));
    mgr.createSession(startMsg('s2'));
    mgr.createSession(startMsg('s3'));
    expect(mgr.activeCount).toBe(3);

    mgr.stopAll();
    expect(mgr.activeCount).toBe(0);
    expect(mgr.getSession('s1')).toBeUndefined();
    expect(mgr.getSession('s2')).toBeUndefined();
    expect(mgr.getSession('s3')).toBeUndefined();
  });
});
