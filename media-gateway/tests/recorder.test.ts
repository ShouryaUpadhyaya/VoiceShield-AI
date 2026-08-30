import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { CallRecorder } from '../src/call-recorder.js';
import fs from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';

describe('CallRecorder', () => {
  const testDir = path.join(__dirname, 'test-recordings');
  let recorder: CallRecorder;

  beforeEach(async () => {
    await fs.mkdir(testDir, { recursive: true });
    recorder = new CallRecorder(testDir);
  });

  afterEach(async () => {
    await fs.rm(testDir, { recursive: true, force: true });
  });

  it('should create a valid WAV file for a 3-second 48kHz mono recording', async () => {
    const sessionId = 'test-session-1';
    const sampleRate = 48000;
    const channels = 1;
    
    recorder.start(sessionId, sampleRate, channels, 'pcm_s16le');
    
    // 3 seconds of 48kHz mono 16-bit PCM = 48000 * 1 * 2 * 3 = 288,000 bytes
    const byteSize = 288000;
    const dummyData = Buffer.alloc(byteSize, 0x01);
    
    recorder.write(sessionId, dummyData);
    
    const info = await recorder.stop(sessionId);
    
    expect(info).not.toBeNull();
    expect(info!.format).toBe('wav');
    expect(info!.durationMs).toBe(3000);
    expect(info!.sizeBytes).toBe(byteSize + 44);
    
    // Verify file exists
    expect(existsSync(info!.path)).toBe(true);
    
    // Read header and verify
    const fileData = await fs.readFile(info!.path);
    expect(fileData.length).toBe(byteSize + 44);
    
    // RIFF header checks
    expect(fileData.subarray(0, 4).toString()).toBe('RIFF');
    expect(fileData.readUInt32LE(4)).toBe(36 + byteSize);
    expect(fileData.subarray(8, 12).toString()).toBe('WAVE');
    
    // fmt chunk
    expect(fileData.subarray(12, 16).toString()).toBe('fmt ');
    expect(fileData.readUInt32LE(16)).toBe(16); // chunk size
    expect(fileData.readUInt16LE(20)).toBe(1); // PCM
    expect(fileData.readUInt16LE(22)).toBe(1); // Channels
    expect(fileData.readUInt32LE(24)).toBe(48000); // Sample Rate
    expect(fileData.readUInt32LE(28)).toBe(48000 * 1 * 2); // Byte Rate
    expect(fileData.readUInt16LE(32)).toBe(2); // Block Align
    expect(fileData.readUInt16LE(34)).toBe(16); // Bits Per Sample
    
    // data chunk
    expect(fileData.subarray(36, 40).toString()).toBe('data');
    expect(fileData.readUInt32LE(40)).toBe(byteSize);
  });

  it('should properly append multiple writes', async () => {
    const sessionId = 'test-session-multi';
    recorder.start(sessionId, 8000, 1, 'pcm_s16le');
    
    // 8000 * 1 * 2 = 16000 bytes/sec
    recorder.write(sessionId, Buffer.alloc(8000, 0x02));
    recorder.write(sessionId, Buffer.alloc(8000, 0x03));
    
    const info = await recorder.stop(sessionId);
    expect(info!.durationMs).toBe(1000);
    expect(info!.sizeBytes).toBe(16000 + 44);
    
    const fileData = await fs.readFile(info!.path);
    expect(fileData.readUInt32LE(40)).toBe(16000); // data chunk length
  });

  it('should return null if no audio is written', async () => {
    const sessionId = 'test-session-empty';
    recorder.start(sessionId, 16000, 1, 'pcm_s16le');
    const info = await recorder.stop(sessionId);
    
    expect(info).toBeNull();
    
    // Ensure temp file is cleaned up
    const tempPath = path.join(testDir, `${sessionId}.pcm.tmp`);
    expect(existsSync(tempPath)).toBe(false);
  });
});
