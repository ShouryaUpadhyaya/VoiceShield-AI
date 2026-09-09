import { describe, expect, it } from 'vitest';
import { pcm16ToWav } from '../src/live-chunk-audio.js';

describe('pcm16ToWav', () => {
  it('creates a playable WAV envelope without altering the chunk payload', () => {
    const pcm = Buffer.from([1, 2, 3, 4]);
    const wav = pcm16ToWav(pcm, 16000, 1);

    expect(wav.subarray(0, 4).toString()).toBe('RIFF');
    expect(wav.subarray(8, 12).toString()).toBe('WAVE');
    expect(wav.readUInt32LE(40)).toBe(pcm.length);
    expect(wav.subarray(44)).toEqual(pcm);
  });
});
