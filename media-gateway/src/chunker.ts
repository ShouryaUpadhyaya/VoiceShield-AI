/**
 * Audio Chunker
 *
 * The MOST CRITICAL component of the media gateway.
 *
 * Buffers arbitrary-sized PCM audio frames and produces exact fixed-duration chunks.
 * Chunk size is calculated from audio format parameters.
 *
 * INVARIANT: totalInputBytes === totalEmittedBytes + remainingBufferedBytes
 *
 * Handles:
 *  - 0 bytes
 *  - 1 byte
 *  - Arbitrary WebSocket frame sizes
 *  - Frames smaller than a chunk
 *  - Frames larger than a chunk (multiple chunks from one frame)
 *  - Chunks split across multiple frames
 *  - Exact chunk boundaries
 *  - Partial final chunks (returned via flush)
 */

export interface ChunkOutput {
  /** The exact-size PCM audio chunk */
  data: Buffer;
  /** Monotonically increasing sequence number (0-based) */
  sequence: number;
  /** Timestamp in ms from session start for this chunk */
  timestampMs: number;
  /** Duration of this chunk in ms */
  durationMs: number;
}

export class AudioChunker {
  /** Target size of each chunk in bytes */
  readonly chunkBytes: number;
  /** Duration of each chunk in ms */
  readonly chunkDurationMs: number;

  private buffer: Buffer = Buffer.alloc(0);
  private sequence: number = 0;
  private totalInputBytes: number = 0;
  private totalEmittedBytes: number = 0;

  /**
   * @param sampleRate    Audio sample rate in Hz (e.g. 16000, 48000)
   * @param channels      Number of audio channels (1 = mono, 2 = stereo)
   * @param bytesPerSample Bytes per sample (2 for PCM 16-bit)
   * @param durationSec   Chunk duration in seconds (e.g. 3)
   */
  constructor(
    public readonly sampleRate: number,
    public readonly channels: number,
    public readonly bytesPerSample: number,
    public readonly durationSec: number,
  ) {
    this.chunkBytes = sampleRate * channels * bytesPerSample * durationSec;
    this.chunkDurationMs = durationSec * 1000;

    if (this.chunkBytes <= 0) {
      throw new Error(
        `Invalid chunk configuration: ${sampleRate}Hz × ${channels}ch × ${bytesPerSample}B × ${durationSec}s = ${this.chunkBytes} bytes`,
      );
    }
  }

  /**
   * Push arbitrary audio data into the chunker.
   * Returns zero or more complete chunks.
   *
   * This is the hot path — it must handle any input size correctly.
   */
  push(data: Buffer): ChunkOutput[] {
    if (data.length === 0) return [];

    this.totalInputBytes += data.length;

    // Append incoming data to the internal buffer
    this.buffer = Buffer.concat([this.buffer, data]);

    const chunks: ChunkOutput[] = [];

    // Extract as many complete chunks as possible
    while (this.buffer.length >= this.chunkBytes) {
      const chunkData = Buffer.alloc(this.chunkBytes);
      this.buffer.copy(chunkData, 0, 0, this.chunkBytes);

      // Slice remaining buffer
      this.buffer = this.buffer.subarray(this.chunkBytes);

      const timestampMs = this.sequence * this.chunkDurationMs;
      chunks.push({
        data: chunkData,
        sequence: this.sequence,
        timestampMs,
        durationMs: this.chunkDurationMs,
      });

      this.sequence++;
      this.totalEmittedBytes += this.chunkBytes;
    }

    return chunks;
  }

  /**
   * Flush any remaining buffered data as a partial chunk.
   * Returns the partial chunk if any data remains, or null.
   * This should be called at session end.
   */
  flush(): ChunkOutput | null {
    if (this.buffer.length === 0) return null;

    const remaining = Buffer.alloc(this.buffer.length);
    this.buffer.copy(remaining);

    const samples = remaining.length / this.bytesPerSample / this.channels;
    const durationMs = (samples / this.sampleRate) * 1000;
    const timestampMs = this.sequence * this.chunkDurationMs;

    const chunk: ChunkOutput = {
      data: remaining,
      sequence: this.sequence,
      timestampMs,
      durationMs: Math.round(durationMs),
    };

    this.totalEmittedBytes += remaining.length;
    this.buffer = Buffer.alloc(0);
    this.sequence++;

    return chunk;
  }

  /** Current sequence number (= number of complete chunks emitted so far). */
  get currentSequence(): number {
    return this.sequence;
  }

  /** Bytes currently buffered (partial chunk). */
  get bufferedBytes(): number {
    return this.buffer.length;
  }

  /** Total bytes received via push(). */
  get inputBytes(): number {
    return this.totalInputBytes;
  }

  /** Total bytes emitted as chunks (including flush). */
  get emittedBytes(): number {
    return this.totalEmittedBytes;
  }

  /**
   * Verify the fundamental invariant:
   *   totalInputBytes === totalEmittedBytes + remainingBufferedBytes
   *
   * Returns true if the invariant holds.
   */
  checkInvariant(): boolean {
    return this.totalInputBytes === this.totalEmittedBytes + this.buffer.length;
  }

  /** Reset the chunker state (for reuse or testing). */
  reset(): void {
    this.buffer = Buffer.alloc(0);
    this.sequence = 0;
    this.totalInputBytes = 0;
    this.totalEmittedBytes = 0;
  }
}
