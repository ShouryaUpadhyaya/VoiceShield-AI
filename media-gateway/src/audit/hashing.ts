import { createHash } from 'node:crypto';
import { canonicalize } from 'json-canonicalize';

export type AuditVerdict = 'DEEPFAKE' | 'AUTHENTIC' | 'UNKNOWN';

export interface EvidenceInput {
  incidentId: string;
  callId: string;
  audioSha256: string;
  recordedAt: string;
  verdict: AuditVerdict;
  /** Decimal text avoids cross-runtime floating-point serialization differences. */
  riskScore: string;
  modelId: string;
  modelVersion: string;
  segmentStartMs: number;
  segmentEndMs: number;
  audioRepresentation: {
    format: string;
    codec: string;
    sampleRateHz: number;
    channels: number;
    bitDepth: number;
  };
}

export interface CanonicalEvidencePayload {
  audio_representation: EvidenceInput['audioRepresentation'];
  audio_sha256: string;
  call_id: string;
  incident_id: string;
  model: { id: string; version: string };
  prediction: { risk_score: string; verdict: AuditVerdict };
  recorded_at: string;
  schema: 'voiceshield.audit.evidence.v1';
  segment: { end_ms: number; start_ms: number };
}

function assertSha256(value: string, field: string): void {
  if (!/^[a-f0-9]{64}$/u.test(value)) {
    throw new Error(`${field} must be a lowercase SHA-256 hex digest`);
  }
}

function assertSafeNonNegativeInteger(value: number, field: string): void {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new Error(`${field} must be a non-negative safe integer`);
  }
}

/** Hash exact persisted bytes or UTF-8 canonical evidence text using SHA-256. */
export function sha256Hex(input: Buffer | string): string {
  return createHash('sha256').update(input).digest('hex');
}

/**
 * Builds the deliberately small, privacy-preserving evidence commitment.
 * Audio and direct identifiers outside internally generated UUIDs never enter it.
 */
export function buildEvidencePayload(input: EvidenceInput): CanonicalEvidencePayload {
  assertSha256(input.audioSha256, 'audioSha256');
  assertSafeNonNegativeInteger(input.segmentStartMs, 'segmentStartMs');
  assertSafeNonNegativeInteger(input.segmentEndMs, 'segmentEndMs');
  if (input.segmentEndMs < input.segmentStartMs) {
    throw new Error('segmentEndMs must not precede segmentStartMs');
  }
  if (!/^(0|[1-9]\d*)(\.\d+)?$/u.test(input.riskScore)) {
    throw new Error('riskScore must be a non-negative decimal string');
  }
  if (Number(input.riskScore) > 100) {
    throw new Error('riskScore must not exceed 100');
  }
  if (Number.isNaN(Date.parse(input.recordedAt))) {
    throw new Error('recordedAt must be an ISO-8601 timestamp');
  }

  return {
    schema: 'voiceshield.audit.evidence.v1',
    incident_id: input.incidentId,
    call_id: input.callId,
    audio_sha256: input.audioSha256,
    recorded_at: input.recordedAt,
    prediction: { verdict: input.verdict, risk_score: input.riskScore },
    model: { id: input.modelId, version: input.modelVersion },
    segment: { start_ms: input.segmentStartMs, end_ms: input.segmentEndMs },
    audio_representation: input.audioRepresentation,
  };
}

/** RFC 8785/JCS canonical JSON representation for the audit preimage. */
export function canonicalizeEvidence(payload: CanonicalEvidencePayload): string {
  return canonicalize(payload);
}

export function evidenceHash(input: EvidenceInput): string {
  return sha256Hex(canonicalizeEvidence(buildEvidencePayload(input)));
}
