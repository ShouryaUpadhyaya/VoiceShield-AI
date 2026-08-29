/**
 * ML WebSocket Client
 *
 * Outbound WebSocket connection to the ML teammate's service.
 * Sends: JSON metadata first, then binary PCM payload for each chunk.
 *
 * Handles:
 *  - Connection / reconnection
 *  - Graceful degradation when ML service is unavailable
 *  - Queuing during brief disconnections
 */

import WebSocket from 'ws';
import type { ChunkOutput } from './chunker.js';
import type { AudioFormat } from './session.js';
import { logger } from './logger.js';
import { persistMlResult } from './persistence.js';

import { EventEmitter } from 'events';

export interface MlChunkMetadata {
  type: 'audio.chunk';
  session_id: string;
  sequence: number;
  timestamp_ms: number;
  duration_ms: number;
  sample_rate: number;
  channels: number;
  encoding: string;
  bytes: number;
}

export class MlClient extends EventEmitter {
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private _isConnected: boolean = false;
  private _url: string;

  /** Reconnect delay in ms */
  private readonly RECONNECT_DELAY_MS = 3000;

  /** Max queued messages during reconnect */
  private readonly MAX_QUEUE_SIZE = 50;

  /** Messages queued while disconnected */
  private sendQueue: Array<{ metadata: MlChunkMetadata; data: Buffer }> = [];

  constructor(url: string) {
    super();
    this._url = url;
  }

  get isConnected(): boolean {
    return this._isConnected;
  }

  /** Connect to the ML service. */
  connect(): void {
    if (this.ws) return;

    logger.info('ML_CONNECTING', { url: this._url });

    try {
      this.ws = new WebSocket(this._url);
    } catch (err) {
      logger.warn('ML_CONNECT_FAILED', { url: this._url, error: String(err) });
      this.scheduleReconnect();
      return;
    }

    this.ws.on('open', () => {
      this._isConnected = true;
      logger.info('ML_CONNECTED', { url: this._url });
      this.drainQueue();
    });

    this.ws.on('message', (data) => {
      try {
        const msg = JSON.parse(data.toString());
        logger.info('ML_RESPONSE', { type: msg.type, session: msg.metadata?.session_id });
        if (msg.type === 'score' && msg.metadata?.session_id) {
          persistMlResult(msg.metadata.session_id, msg.window_seq, msg);
          this.emit('score', msg);
        }
      } catch {
        logger.debug('ML_RAW_RESPONSE', { size: (data as Buffer).length });
      }
    });

    this.ws.on('close', (code, reason) => {
      this._isConnected = false;
      this.ws = null;
      logger.warn('ML_DISCONNECTED', { code, reason: reason.toString() });
      this.scheduleReconnect();
    });

    this.ws.on('error', (err) => {
      logger.error('ML_ERROR', { error: err.message });
      // The 'close' event will fire after this
    });
  }

  /**
   * Send a chunk to the ML service.
   * Protocol: JSON metadata frame, then binary PCM frame.
   */
  sendChunk(
    sessionId: string,
    chunk: ChunkOutput,
    format: AudioFormat,
  ): void {
    const metadata: MlChunkMetadata = {
      type: 'audio.chunk',
      session_id: sessionId,
      sequence: chunk.sequence,
      timestamp_ms: chunk.timestampMs,
      duration_ms: chunk.durationMs,
      sample_rate: format.sampleRate,
      channels: format.channels,
      encoding: format.encoding,
      bytes: chunk.data.length,
    };

    if (this._isConnected && this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(metadata));
      this.ws.send(chunk.data);
      logger.info('ML_SENT', {
        session: sessionId,
        seq: chunk.sequence,
        bytes: chunk.data.length,
      });
    } else {
      // Queue for when connection is restored
      if (this.sendQueue.length < this.MAX_QUEUE_SIZE) {
        this.sendQueue.push({ metadata, data: chunk.data });
        logger.warn('ML_QUEUED', {
          session: sessionId,
          seq: chunk.sequence,
          queueSize: this.sendQueue.length,
        });
      } else {
        logger.error('ML_QUEUE_FULL', {
          session: sessionId,
          seq: chunk.sequence,
          dropped: true,
        });
      }
    }
  }

  /** Disconnect from the ML service. */
  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this._isConnected = false;
    this.sendQueue = [];
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.ws = null;
      this.connect();
    }, this.RECONNECT_DELAY_MS);
  }

  private drainQueue(): void {
    if (this.sendQueue.length === 0) return;
    logger.info('ML_DRAINING_QUEUE', { count: this.sendQueue.length });

    while (this.sendQueue.length > 0 && this._isConnected && this.ws?.readyState === WebSocket.OPEN) {
      const item = this.sendQueue.shift()!;
      this.ws.send(JSON.stringify(item.metadata));
      this.ws.send(item.data);
      logger.info('ML_SENT', {
        session: item.metadata.session_id,
        seq: item.metadata.sequence,
        bytes: item.data.length,
        fromQueue: true,
      });
    }
  }
}
