/**
 * Protocol Parser Tests
 */

import { describe, it, expect } from 'vitest';
import { validateProtocolMessage, ProtocolError } from '../src/protocol.js';

describe('Protocol Parser', () => {
  describe('session.start', () => {
    it('parses a valid session.start', () => {
      const msg = validateProtocolMessage({
        type: 'session.start',
        session_id: 'abc-123',
        source: 'callvault',
        sample_rate: 16000,
        channels: 1,
        encoding: 'pcm_s16le',
      });
      expect(msg.type).toBe('session.start');
      if (msg.type === 'session.start') {
        expect(msg.session_id).toBe('abc-123');
        expect(msg.source).toBe('callvault');
        expect(msg.sample_rate).toBe(16000);
        expect(msg.channels).toBe(1);
        expect(msg.encoding).toBe('pcm_s16le');
      }
    });

    it('accepts all supported sample rates', () => {
      for (const rate of [8000, 16000, 44100, 48000]) {
        const msg = validateProtocolMessage({
          type: 'session.start',
          session_id: 'test',
          source: 'test',
          sample_rate: rate,
          channels: 1,
          encoding: 'pcm_s16le',
        });
        expect(msg.type).toBe('session.start');
      }
    });

    it('rejects missing session_id', () => {
      expect(() => validateProtocolMessage({
        type: 'session.start',
        source: 'test',
        sample_rate: 16000,
        channels: 1,
        encoding: 'pcm_s16le',
      })).toThrow(ProtocolError);
      try {
        validateProtocolMessage({
          type: 'session.start', source: 'test', sample_rate: 16000, channels: 1, encoding: 'pcm_s16le',
        });
      } catch (e) {
        expect((e as ProtocolError).code).toBe('MISSING_SESSION_ID');
      }
    });

    it('rejects empty session_id', () => {
      try {
        validateProtocolMessage({
          type: 'session.start', session_id: '', source: 'test', sample_rate: 16000, channels: 1, encoding: 'pcm_s16le',
        });
        expect.fail('should throw');
      } catch (e) {
        expect(e).toBeInstanceOf(ProtocolError);
        expect((e as ProtocolError).code).toBe('MISSING_SESSION_ID');
      }
    });

    it('rejects missing source', () => {
      try {
        validateProtocolMessage({
          type: 'session.start', session_id: 'x', sample_rate: 16000, channels: 1, encoding: 'pcm_s16le',
        });
        expect.fail('should throw');
      } catch (e) {
        expect((e as ProtocolError).code).toBe('MISSING_SOURCE');
      }
    });

    it('rejects missing sample_rate', () => {
      try {
        validateProtocolMessage({
          type: 'session.start', session_id: 'x', source: 'test', channels: 1, encoding: 'pcm_s16le',
        });
        expect.fail('should throw');
      } catch (e) {
        expect((e as ProtocolError).code).toBe('MISSING_SAMPLE_RATE');
      }
    });

    it('rejects unsupported sample_rate', () => {
      try {
        validateProtocolMessage({
          type: 'session.start', session_id: 'x', source: 'test', sample_rate: 22050, channels: 1, encoding: 'pcm_s16le',
        });
        expect.fail('should throw');
      } catch (e) {
        expect((e as ProtocolError).code).toBe('UNSUPPORTED_SAMPLE_RATE');
      }
    });

    it('rejects missing channels', () => {
      try {
        validateProtocolMessage({
          type: 'session.start', session_id: 'x', source: 'test', sample_rate: 16000, encoding: 'pcm_s16le',
        });
        expect.fail('should throw');
      } catch (e) {
        expect((e as ProtocolError).code).toBe('MISSING_CHANNELS');
      }
    });

    it('rejects unsupported channels', () => {
      try {
        validateProtocolMessage({
          type: 'session.start', session_id: 'x', source: 'test', sample_rate: 16000, channels: 5, encoding: 'pcm_s16le',
        });
        expect.fail('should throw');
      } catch (e) {
        expect((e as ProtocolError).code).toBe('UNSUPPORTED_CHANNELS');
      }
    });

    it('rejects missing encoding', () => {
      try {
        validateProtocolMessage({
          type: 'session.start', session_id: 'x', source: 'test', sample_rate: 16000, channels: 1,
        });
        expect.fail('should throw');
      } catch (e) {
        expect((e as ProtocolError).code).toBe('MISSING_ENCODING');
      }
    });

    it('rejects unsupported encoding', () => {
      try {
        validateProtocolMessage({
          type: 'session.start', session_id: 'x', source: 'test', sample_rate: 16000, channels: 1, encoding: 'mp3',
        });
        expect.fail('should throw');
      } catch (e) {
        expect((e as ProtocolError).code).toBe('UNSUPPORTED_ENCODING');
      }
    });
  });

  describe('session.stop', () => {
    it('parses a valid session.stop', () => {
      const msg = validateProtocolMessage({
        type: 'session.stop',
        session_id: 'abc-123',
      });
      expect(msg.type).toBe('session.stop');
      if (msg.type === 'session.stop') {
        expect(msg.session_id).toBe('abc-123');
      }
    });

    it('rejects missing session_id', () => {
      try {
        validateProtocolMessage({ type: 'session.stop' });
        expect.fail('should throw');
      } catch (e) {
        expect((e as ProtocolError).code).toBe('MISSING_SESSION_ID');
      }
    });
  });

  describe('malformed messages', () => {
    it('rejects non-object (string)', () => {
      try {
        validateProtocolMessage('just a string');
        expect.fail('should throw');
      } catch (e) {
        expect((e as ProtocolError).code).toBe('NOT_OBJECT');
      }
    });

    it('rejects null', () => {
      try {
        validateProtocolMessage(null);
        expect.fail('should throw');
      } catch (e) {
        expect((e as ProtocolError).code).toBe('NOT_OBJECT');
      }
    });

    it('rejects missing type', () => {
      try {
        validateProtocolMessage({ session_id: 'x' });
        expect.fail('should throw');
      } catch (e) {
        expect((e as ProtocolError).code).toBe('MISSING_TYPE');
      }
    });

    it('rejects unknown type', () => {
      try {
        validateProtocolMessage({ type: 'session.pause' });
        expect.fail('should throw');
      } catch (e) {
        expect((e as ProtocolError).code).toBe('UNKNOWN_TYPE');
      }
    });
  });
});
