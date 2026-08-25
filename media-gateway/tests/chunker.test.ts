/**
 * AudioChunker Tests — the MOST CRITICAL test suite.
 *
 * Tests the fundamental invariant:
 *   totalInputBytes === totalEmittedBytes + remainingBufferedBytes
 */

import { describe, it, expect } from 'vitest';
import { AudioChunker } from '../src/chunker.js';

// 16kHz mono PCM16: chunkBytes = 16000 × 1 × 2 × 3 = 96000
const RATE = 16000;
const CH = 1;
const BPS = 2;
const DUR = 3;
const CHUNK = RATE * CH * BPS * DUR; // 96000

function make(size: number, fill = 0xAB): Buffer {
  return Buffer.alloc(size, fill);
}

function chunker(): AudioChunker {
  return new AudioChunker(RATE, CH, BPS, DUR);
}

describe('AudioChunker', () => {
  it('calculates chunk size from audio format', () => {
    const c = chunker();
    expect(c.chunkBytes).toBe(96000);
    expect(c.chunkDurationMs).toBe(3000);
  });

  it('0 bytes → no chunks', () => {
    const c = chunker();
    const out = c.push(Buffer.alloc(0));
    expect(out).toHaveLength(0);
    expect(c.bufferedBytes).toBe(0);
    expect(c.checkInvariant()).toBe(true);
  });

  it('1 byte → no chunks, 1 buffered', () => {
    const c = chunker();
    const out = c.push(make(1));
    expect(out).toHaveLength(0);
    expect(c.bufferedBytes).toBe(1);
    expect(c.checkInvariant()).toBe(true);
  });

  it('95,999 bytes → no chunks, 95999 buffered', () => {
    const c = chunker();
    const out = c.push(make(CHUNK - 1));
    expect(out).toHaveLength(0);
    expect(c.bufferedBytes).toBe(CHUNK - 1);
    expect(c.checkInvariant()).toBe(true);
  });

  it('exactly 96,000 bytes → 1 chunk, 0 buffered', () => {
    const c = chunker();
    const out = c.push(make(CHUNK));
    expect(out).toHaveLength(1);
    expect(out[0].data.length).toBe(CHUNK);
    expect(out[0].sequence).toBe(0);
    expect(c.bufferedBytes).toBe(0);
    expect(c.checkInvariant()).toBe(true);
  });

  it('96,001 bytes → 1 chunk, 1 buffered', () => {
    const c = chunker();
    const out = c.push(make(CHUNK + 1));
    expect(out).toHaveLength(1);
    expect(out[0].sequence).toBe(0);
    expect(c.bufferedBytes).toBe(1);
    expect(c.checkInvariant()).toBe(true);
  });

  it('192,000 bytes → 2 chunks, 0 buffered', () => {
    const c = chunker();
    const out = c.push(make(CHUNK * 2));
    expect(out).toHaveLength(2);
    expect(out[0].sequence).toBe(0);
    expect(out[1].sequence).toBe(1);
    expect(c.bufferedBytes).toBe(0);
    expect(c.checkInvariant()).toBe(true);
  });

  it('250,000 bytes → 2 chunks, 58000 buffered', () => {
    const c = chunker();
    const out = c.push(make(250_000));
    expect(out).toHaveLength(2);
    expect(c.bufferedBytes).toBe(250_000 - CHUNK * 2); // 58000
    expect(c.bufferedBytes).toBe(58000);
    expect(c.checkInvariant()).toBe(true);
  });

  it('one byte at a time → 1 chunk after 96000 pushes', () => {
    const c = chunker();
    let totalChunks = 0;
    for (let i = 0; i < CHUNK; i++) {
      const out = c.push(make(1));
      totalChunks += out.length;
    }
    expect(totalChunks).toBe(1);
    expect(c.bufferedBytes).toBe(0);
    expect(c.currentSequence).toBe(1);
    expect(c.checkInvariant()).toBe(true);
  });

  it('multiple chunks in one push (300,000 bytes)', () => {
    const c = chunker();
    const out = c.push(make(300_000));
    expect(out).toHaveLength(3); // 3 × 96000 = 288000
    expect(c.bufferedBytes).toBe(300_000 - CHUNK * 3); // 12000
    expect(c.bufferedBytes).toBe(12000);
    expect(c.checkInvariant()).toBe(true);
  });

  it('partial chunks across multiple pushes', () => {
    const c = chunker();
    // Push 50000, then 50000 → 1 chunk, 4000 remaining
    const out1 = c.push(make(50000));
    expect(out1).toHaveLength(0);
    expect(c.bufferedBytes).toBe(50000);

    const out2 = c.push(make(50000));
    expect(out2).toHaveLength(1);
    expect(out2[0].sequence).toBe(0);
    expect(c.bufferedBytes).toBe(4000);
    expect(c.checkInvariant()).toBe(true);
  });

  it('flush returns partial data', () => {
    const c = chunker();
    c.push(make(50000));
    const flushed = c.flush();
    expect(flushed).not.toBeNull();
    expect(flushed!.data.length).toBe(50000);
    expect(c.bufferedBytes).toBe(0);
    expect(c.checkInvariant()).toBe(true);
  });

  it('flush with empty buffer returns null', () => {
    const c = chunker();
    expect(c.flush()).toBeNull();
  });

  it('flush after exact chunk returns null', () => {
    const c = chunker();
    c.push(make(CHUNK));
    expect(c.flush()).toBeNull();
  });

  it('sequence numbers are monotonic starting from 0', () => {
    const c = chunker();
    const out = c.push(make(CHUNK * 5));
    expect(out).toHaveLength(5);
    for (let i = 0; i < 5; i++) {
      expect(out[i].sequence).toBe(i);
    }
  });

  it('timestamps are correct', () => {
    const c = chunker();
    const out = c.push(make(CHUNK * 3));
    expect(out[0].timestampMs).toBe(0);
    expect(out[1].timestampMs).toBe(3000);
    expect(out[2].timestampMs).toBe(6000);
    for (const chunk of out) {
      expect(chunk.durationMs).toBe(3000);
    }
  });

  it('works with 48kHz mono', () => {
    const c48 = new AudioChunker(48000, 1, 2, 3);
    expect(c48.chunkBytes).toBe(288000);
    const out = c48.push(make(288000));
    expect(out).toHaveLength(1);
    expect(out[0].data.length).toBe(288000);
    expect(c48.checkInvariant()).toBe(true);
  });

  it('preserves actual byte content', () => {
    const c = chunker();
    // Fill with a known pattern: bytes 0,1,2,...,255,0,1,...
    const input = Buffer.alloc(CHUNK);
    for (let i = 0; i < CHUNK; i++) {
      input[i] = i % 256;
    }
    const out = c.push(input);
    expect(out).toHaveLength(1);
    expect(Buffer.compare(out[0].data, input)).toBe(0);
  });

  it('invariant holds through complex sequence', () => {
    const c = chunker();
    // Simulate realistic usage: many irregular pushes
    const sizes = [100, 4096, 32000, 1, 60000, 96000, 50, 4000, 92000, 10000];
    for (const size of sizes) {
      c.push(make(size));
      expect(c.checkInvariant()).toBe(true);
    }
    c.flush();
    expect(c.checkInvariant()).toBe(true);
    // Verify total accounting
    const totalIn = sizes.reduce((a, b) => a + b, 0);
    expect(c.inputBytes).toBe(totalIn);
    expect(c.emittedBytes + c.bufferedBytes).toBe(totalIn);
  });

  it('10 seconds of 16kHz mono → 3 chunks + remainder', () => {
    const c = chunker();
    const tenSec = RATE * CH * BPS * 10; // 320,000
    const out = c.push(make(tenSec));
    expect(out).toHaveLength(3);
    expect(c.bufferedBytes).toBe(tenSec - CHUNK * 3); // 32,000
    expect(c.checkInvariant()).toBe(true);
  });

  it('30 seconds of 16kHz mono → 10 chunks exactly', () => {
    const c = chunker();
    const thirtySec = RATE * CH * BPS * 30; // 960,000
    const out = c.push(make(thirtySec));
    expect(out).toHaveLength(10);
    expect(c.bufferedBytes).toBe(0);
    expect(c.checkInvariant()).toBe(true);
  });
});
