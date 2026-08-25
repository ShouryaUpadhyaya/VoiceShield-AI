/**
 * Session Manager
 *
 * Manages audio sessions — one per WebSocket connection from an audio source.
 * Each session has its own chunker, sequence counter, and metadata.
 *
 * Sessions are isolated: audio from session A NEVER reaches session B.
 */

import { AudioChunker, type ChunkOutput } from './chunker.js';
import { type SessionStartMessage, type SupportedEncoding } from './protocol.js';
import { bytesPerSampleForEncoding, calculateChunkBytes } from './config.js';
import { logger } from './logger.js';

// ── Session states ─────────────────────────────────────────────────

export type SessionStatus = 'CONNECTED' | 'STREAMING' | 'STOPPING' | 'COMPLETED' | 'ERROR';

export interface AudioFormat {
  sampleRate: number;
  channels: number;
  encoding: SupportedEncoding;
  bytesPerSample: number;
}

export interface SessionInfo {
  sessionId: string;
  source: string;
  createdAt: Date;
  format: AudioFormat;
  chunkSequence: number;
  bufferedBytes: number;
  status: SessionStatus;
  totalBytesReceived: number;
  totalChunksEmitted: number;
}

// ── Session class ──────────────────────────────────────────────────

export class AudioSession {
  readonly sessionId: string;
  readonly source: string;
  readonly createdAt: Date;
  readonly format: AudioFormat;
  readonly chunker: AudioChunker;

  private _status: SessionStatus = 'CONNECTED';
  private _totalBytesReceived: number = 0;

  constructor(startMsg: SessionStartMessage, chunkDurationSec: number) {
    this.sessionId = startMsg.session_id;
    this.source = startMsg.source;
    this.createdAt = new Date();

    const bps = bytesPerSampleForEncoding(startMsg.encoding);
    this.format = {
      sampleRate: startMsg.sample_rate,
      channels: startMsg.channels,
      encoding: startMsg.encoding,
      bytesPerSample: bps,
    };

    this.chunker = new AudioChunker(
      startMsg.sample_rate,
      startMsg.channels,
      bps,
      chunkDurationSec,
    );

    this._status = 'STREAMING';

    logger.info('SESSION_START', {
      session: this.sessionId,
      source: this.source,
      rate: startMsg.sample_rate,
      channels: startMsg.channels,
      encoding: startMsg.encoding,
      chunkBytes: this.chunker.chunkBytes,
    });
  }

  /** Push audio data and return any complete chunks. */
  pushAudio(data: Buffer): ChunkOutput[] {
    if (this._status !== 'STREAMING') {
      logger.warn('AUDIO_IGNORED', {
        session: this.sessionId,
        status: this._status,
        bytes: data.length,
      });
      return [];
    }

    this._totalBytesReceived += data.length;

    logger.debug('AUDIO_RECEIVED', {
      session: this.sessionId,
      bytes: data.length,
      total: this._totalBytesReceived,
    });

    const chunks = this.chunker.push(data);

    for (const chunk of chunks) {
      logger.info('CHUNK_CREATED', {
        session: this.sessionId,
        seq: chunk.sequence,
        bytes: chunk.data.length,
        timestampMs: chunk.timestampMs,
      });
    }

    return chunks;
  }

  /** Stop the session and flush any remaining audio. */
  stop(): ChunkOutput | null {
    if (this._status === 'COMPLETED' || this._status === 'ERROR') {
      logger.warn('SESSION_ALREADY_STOPPED', { session: this.sessionId, status: this._status });
      return null;
    }

    this._status = 'STOPPING';
    const partial = this.chunker.flush();

    if (partial) {
      logger.info('CHUNK_FLUSHED', {
        session: this.sessionId,
        seq: partial.sequence,
        bytes: partial.data.length,
        durationMs: partial.durationMs,
      });
    }

    this._status = 'COMPLETED';

    logger.info('SESSION_STOP', {
      session: this.sessionId,
      totalBytes: this._totalBytesReceived,
      totalChunks: this.chunker.currentSequence,
      invariantOk: this.chunker.checkInvariant(),
    });

    return partial;
  }

  /** Mark session as errored. */
  setError(): void {
    this._status = 'ERROR';
  }

  get status(): SessionStatus {
    return this._status;
  }

  get totalBytesReceived(): number {
    return this._totalBytesReceived;
  }

  /** Snapshot of session info for health/debug endpoints. */
  toInfo(): SessionInfo {
    return {
      sessionId: this.sessionId,
      source: this.source,
      createdAt: this.createdAt,
      format: { ...this.format },
      chunkSequence: this.chunker.currentSequence,
      bufferedBytes: this.chunker.bufferedBytes,
      status: this._status,
      totalBytesReceived: this._totalBytesReceived,
      totalChunksEmitted: this.chunker.currentSequence,
    };
  }
}

// ── Session Manager ────────────────────────────────────────────────

export class SessionManager {
  private sessions = new Map<string, AudioSession>();

  constructor(private readonly chunkDurationSec: number) {}

  /** Create and register a new session. Throws if session ID already exists. */
  createSession(startMsg: SessionStartMessage): AudioSession {
    if (this.sessions.has(startMsg.session_id)) {
      throw new Error(`Session already exists: ${startMsg.session_id}`);
    }

    const session = new AudioSession(startMsg, this.chunkDurationSec);
    this.sessions.set(startMsg.session_id, session);
    return session;
  }

  /** Get a session by ID, or undefined if it doesn't exist. */
  getSession(sessionId: string): AudioSession | undefined {
    return this.sessions.get(sessionId);
  }

  /** Remove a session from the manager. */
  removeSession(sessionId: string): boolean {
    return this.sessions.delete(sessionId);
  }

  /** Number of active sessions. */
  get activeCount(): number {
    let count = 0;
    for (const session of this.sessions.values()) {
      if (session.status === 'STREAMING' || session.status === 'CONNECTED') {
        count++;
      }
    }
    return count;
  }

  /** All sessions info (for health endpoint). */
  getSessionInfos(): SessionInfo[] {
    return Array.from(this.sessions.values()).map((s) => s.toInfo());
  }

  /** Stop all active sessions and clean up. */
  stopAll(): void {
    for (const session of this.sessions.values()) {
      if (session.status === 'STREAMING') {
        session.stop();
      }
    }
    this.sessions.clear();
  }
}
