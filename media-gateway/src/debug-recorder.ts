/**
 * Debug Audio Recorder
 *
 * When SAVE_DEBUG_AUDIO=true, saves raw PCM received by the gateway to disk.
 * Strictly a hackathon debugging tool — not a production storage system.
 *
 * Lets us compare:
 *   CallVault local recording  vs  Gateway recording  vs  ML payload
 */

import { mkdirSync, createWriteStream, type WriteStream } from 'node:fs';
import { join } from 'node:path';
import { logger } from './logger.js';

export class DebugRecorder {
  private writers = new Map<string, WriteStream>();
  private readonly dir: string;

  constructor(dir: string) {
    this.dir = dir;
    mkdirSync(dir, { recursive: true });
  }

  /** Start recording for a session. */
  start(sessionId: string, sampleRate: number, channels: number, encoding: string): void {
    const filename = `${sessionId}_${sampleRate}hz_${channels}ch_${encoding}.pcm`;
    const filepath = join(this.dir, filename);
    const writer = createWriteStream(filepath);
    this.writers.set(sessionId, writer);
    logger.info('DEBUG_RECORD_START', { session: sessionId, path: filepath });
  }

  /** Write audio data for a session. */
  write(sessionId: string, data: Buffer): void {
    const writer = this.writers.get(sessionId);
    if (writer) {
      writer.write(data);
    }
  }

  /** Stop recording for a session. */
  stop(sessionId: string): void {
    const writer = this.writers.get(sessionId);
    if (writer) {
      writer.end();
      this.writers.delete(sessionId);
      logger.info('DEBUG_RECORD_STOP', { session: sessionId });
    }
  }

  /** Stop all recordings. */
  stopAll(): void {
    for (const [sessionId, writer] of this.writers.entries()) {
      writer.end();
      logger.info('DEBUG_RECORD_STOP', { session: sessionId });
    }
    this.writers.clear();
  }
}
