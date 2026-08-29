import 'dotenv/config';
import { describe, it, expect, beforeEach } from 'vitest';
import { persistSessionStart, persistChunk, persistMlResult, prisma } from '../src/persistence.js';

describe('ML Integration Persistence E2E', () => {
  beforeEach(async () => {
    // Clear relevant tables
    await prisma.ml_results.deleteMany();
    await prisma.audio_chunks.deleteMany();
    await prisma.audio_streams.deleteMany();
    await prisma.connection_events.deleteMany();
    await prisma.recordings.deleteMany();
    await prisma.calls.deleteMany();
  });

  it('should successfully store an ML result against an audio chunk', async () => {
    const sessionId = 'test-ml-session-' + Date.now();
    const callId = 'test-ml-call-' + Date.now();

    // Start session
    persistSessionStart({
      sessionId,
      source: 'test-source',
      format: { sampleRate: 16000, channels: 1, encoding: 'pcm_s16le' },
      chunkBytes: 96000,
      rms: 0,
      totalBytesReceived: 0
    }, callId);

    // Give it a moment to process queue
    await new Promise(r => setTimeout(r, 100));

    // Save a chunk
    persistChunk(callId, {
      sequence: 0,
      timestampMs: 0,
      durationMs: 3000,
      data: Buffer.alloc(96000)
    });

    await new Promise(r => setTimeout(r, 100));

    // Persist ML result
    const mlResponse = {
      backend: 'dhwani+ecapa',
      inference_ms: 152,
      status: 'OK',
      signals: {
        deepfake_probability: 0.85,
        speaker_match: { speaker_id: 'user_123', distance: 0.2 },
        prosody_analysis: { overall_prosody_risk: 0.1 }
      }
    };
    persistMlResult(sessionId, 0, mlResponse);

    await new Promise(r => setTimeout(r, 100));

    // Verify DB
    const chunk = await prisma.audio_chunks.findFirst({
      where: { call_id: callId, sequence_number: 0 }
    });
    
    expect(chunk).toBeDefined();
    expect(chunk?.processing_progress).toBe('completed');

    const result = await prisma.ml_results.findFirst({
      where: { audio_chunk_id: chunk!.id }
    });

    expect(result).toBeDefined();
    expect(result?.is_deepfake).toBe(true);
    expect(result?.speaker_id).toBe('user_123');
    expect(result?.latency_ms).toBe(152);
  });
});
