import { describe, expect, it } from 'vitest';
import {
  canonicalizeEvidence,
  sha256Hex,
  buildEvidencePayload,
} from '../src/audit/hashing.js';

describe('audit evidence hashing', () => {
  const evidence = {
    incidentId: '9f20e619-6064-4b30-93d8-6f2bd6d65967',
    callId: '5e25f75b-ece5-49ba-a9fd-58f0eb69e6b9',
    audioSha256: sha256Hex(Buffer.from([0, 1, 2, 3])),
    recordedAt: '2026-09-09T10:12:13.000Z',
    verdict: 'DEEPFAKE' as const,
    riskScore: '94.21',
    modelId: 'voiceshield-fusion',
    modelVersion: '1.3.0',
    segmentStartMs: 39000,
    segmentEndMs: 42000,
    audioRepresentation: {
      format: 'wav',
      codec: 'pcm_s16le',
      sampleRateHz: 48000,
      channels: 1,
      bitDepth: 16,
    },
  };

  it('is deterministic regardless of input object key order', () => {
    const payload = buildEvidencePayload(evidence);
    const reordered = {
      segment: { start_ms: payload.segment.start_ms, end_ms: payload.segment.end_ms },
      schema: payload.schema,
      recorded_at: payload.recorded_at,
      prediction: { verdict: payload.prediction.verdict, risk_score: payload.prediction.risk_score },
      model: { version: payload.model.version, id: payload.model.id },
      incident_id: payload.incident_id,
      call_id: payload.call_id,
      audio_sha256: payload.audio_sha256,
      audio_representation: {
        bitDepth: payload.audio_representation.bitDepth,
        channels: payload.audio_representation.channels,
        sampleRateHz: payload.audio_representation.sampleRateHz,
        codec: payload.audio_representation.codec,
        format: payload.audio_representation.format,
      },
    };

    expect(canonicalizeEvidence(payload)).toBe(canonicalizeEvidence(reordered));
    expect(sha256Hex(canonicalizeEvidence(payload))).toBe(sha256Hex(canonicalizeEvidence(reordered)));
  });

  it('changes the evidence hash when one official audio byte changes', () => {
    expect(sha256Hex(Buffer.from([0, 1, 2, 3]))).not.toBe(sha256Hex(Buffer.from([0, 1, 2, 4])));
  });

  it('commits to verdict, risk score, and model version', () => {
    const baseline = sha256Hex(canonicalizeEvidence(buildEvidencePayload(evidence)));

    for (const changed of [
      { ...evidence, verdict: 'AUTHENTIC' as const },
      { ...evidence, riskScore: '94.22' },
      { ...evidence, modelVersion: '1.3.1' },
    ]) {
      expect(sha256Hex(canonicalizeEvidence(buildEvidencePayload(changed)))).not.toBe(baseline);
    }
  });
});
