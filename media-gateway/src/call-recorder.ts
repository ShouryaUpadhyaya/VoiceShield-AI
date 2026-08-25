import { mkdirSync, createWriteStream, WriteStream } from 'node:fs';
import { join } from 'node:path';
import { logger } from './logger.js';
import fs from 'node:fs/promises';

export interface RecordingInfo {
  path: string;
  format: string;
  sizeBytes: number;
  durationMs: number;
}

export class CallRecorder {
  private writers = new Map<string, {
    stream: WriteStream;
    path: string;
    sampleRate: number;
    channels: number;
    bytesPerSample: number;
    totalBytes: number;
  }>();

  constructor(private readonly baseDir: string) {
    mkdirSync(baseDir, { recursive: true });
  }

  start(sessionId: string, sampleRate: number, channels: number, encoding: string): void {
    const bps = encoding === 'pcm_s16le' ? 2 : 2;
    const tempPath = join(this.baseDir, `${sessionId}.pcm.tmp`);
    
    const stream = createWriteStream(tempPath);
    this.writers.set(sessionId, {
      stream,
      path: tempPath,
      sampleRate,
      channels,
      bytesPerSample: bps,
      totalBytes: 0,
    });
    
    logger.info('RECORDING_STARTED', { session: sessionId, tempPath });
  }

  write(sessionId: string, data: Buffer): void {
    const session = this.writers.get(sessionId);
    if (session) {
      session.stream.write(data);
      session.totalBytes += data.length;
    }
  }

  async stop(sessionId: string): Promise<RecordingInfo | null> {
    const session = this.writers.get(sessionId);
    if (!session) return null;

    return new Promise((resolve) => {
      session.stream.end(async () => {
        this.writers.delete(sessionId);
        
        try {
          if (session.totalBytes === 0) {
            await fs.unlink(session.path);
            return resolve(null);
          }

          // Generate WAV header
          const finalPath = join(this.baseDir, `${sessionId}.wav`);
          const wavHeader = this.createWavHeader(session.totalBytes, session.sampleRate, session.channels, session.bytesPerSample * 8);
          
          const finalHandle = await fs.open(finalPath, 'w');
          await finalHandle.write(wavHeader);
          
          const tempHandle = await fs.open(session.path, 'r');
          const buffer = Buffer.alloc(64 * 1024);
          let bytesRead;
          while ((bytesRead = (await tempHandle.read(buffer, 0, buffer.length, null)).bytesRead) > 0) {
            await finalHandle.write(buffer, 0, bytesRead);
          }
          await tempHandle.close();
          await finalHandle.close();
          
          await fs.unlink(session.path);

          const durationMs = Math.floor((session.totalBytes / (session.sampleRate * session.channels * session.bytesPerSample)) * 1000);

          logger.info('RECORDING_SAVED', { session: sessionId, finalPath, bytes: session.totalBytes, durationMs });

          resolve({
            path: finalPath,
            format: 'wav',
            sizeBytes: session.totalBytes + 44, // 44 bytes header
            durationMs
          });
        } catch (err) {
          logger.error('RECORDING_ERROR', { session: sessionId, error: String(err) });
          resolve(null);
        }
      });
    });
  }
  
  stopAll(): void {
    for (const [sessionId, session] of this.writers.entries()) {
      session.stream.end();
      this.writers.delete(sessionId);
    }
  }

  private createWavHeader(dataLength: number, sampleRate: number, channels: number, bitsPerSample: number): Buffer {
    const header = Buffer.alloc(44);
    header.write('RIFF', 0);
    header.writeUInt32LE(36 + dataLength, 4);
    header.write('WAVE', 8);
    header.write('fmt ', 12);
    header.writeUInt32LE(16, 16);
    header.writeUInt16LE(1, 20);
    header.writeUInt16LE(channels, 22);
    header.writeUInt32LE(sampleRate, 24);
    header.writeUInt32LE(sampleRate * channels * (bitsPerSample / 8), 28);
    header.writeUInt16LE(channels * (bitsPerSample / 8), 32);
    header.writeUInt16LE(bitsPerSample, 34);
    header.write('data', 36);
    header.writeUInt32LE(dataLength, 40);
    return header;
  }
}
