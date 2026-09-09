import { buildEvidencePayload, canonicalizeEvidence, sha256Hex, type AuditVerdict } from './hashing.js';

export type AuditState = 'PENDING' | 'SUBMITTED' | 'CONFIRMED' | 'FAILED' | 'VERIFIED' | 'MISMATCH' | 'NOT_ANCHORED';

export interface AuditSnapshot {
  audioBytes: Buffer;
  riskScore: string;
  verdict: AuditVerdict;
  modelId: string;
  modelVersion: string;
  recordedAt: string;
  segmentStartMs?: number;
  segmentEndMs?: number;
}

export interface AuditRepository {
  getPending(id: string): Promise<any | null>;
  getSnapshot(record: any): Promise<AuditSnapshot>;
  markSubmitted(id: string, data: { audioHash: string; evidenceHash: string; riskScore: string; verdict: AuditVerdict; modelId: string; modelVersion: string }): Promise<void>;
  markConfirmed(id: string, proof: any): Promise<void>;
  markFailed(id: string, error: string): Promise<void>;
  markNotAnchored?(id: string): Promise<void>;
  findByCallId?(callId: string): Promise<any | null>;
  markVerification?(id: string, state: AuditState): Promise<void>;
}

export interface BlockchainClient {
  enabled: boolean;
  anchor(evidenceId: string, evidenceHash: string): Promise<any>;
  get?(evidenceId: string): Promise<{ evidenceHash: string; anchoredAt: Date } | null>;
}

function materialize(record: any, snapshot: AuditSnapshot) {
  const audioHash = sha256Hex(snapshot.audioBytes);
  const payload = buildEvidencePayload({
    incidentId: record.evidence_id,
    callId: record.call_id,
    audioSha256: audioHash,
    recordedAt: snapshot.recordedAt,
    verdict: snapshot.verdict,
    riskScore: snapshot.riskScore,
    modelId: snapshot.modelId,
    modelVersion: snapshot.modelVersion,
    segmentStartMs: snapshot.segmentStartMs ?? 0,
    segmentEndMs: snapshot.segmentEndMs ?? 0,
    audioRepresentation: {
      format: record.recording_format,
      codec: 'pcm_s16le',
      sampleRateHz: record.sample_rate_hz,
      channels: record.channels,
      bitDepth: record.bit_depth,
    },
  });
  return { audioHash, evidenceHash: sha256Hex(canonicalizeEvidence(payload)), riskScore: snapshot.riskScore, verdict: snapshot.verdict, modelId: snapshot.modelId, modelVersion: snapshot.modelVersion };
}

export class AuditService {
  constructor(private readonly repository: AuditRepository, private readonly blockchain: BlockchainClient) {}

  async process(auditId: string): Promise<void> {
    const record = await this.repository.getPending(auditId);
    if (!record) return;
    if (!this.blockchain.enabled) {
      await this.repository.markNotAnchored?.(auditId);
      return;
    }
    try {
      const material = materialize(record, await this.repository.getSnapshot(record));
      await this.repository.markSubmitted(auditId, material);
      const proof = await this.blockchain.anchor(record.evidence_id, material.evidenceHash);
      await this.repository.markConfirmed(auditId, { ...proof, ...material });
    } catch (error) {
      await this.repository.markFailed(auditId, error instanceof Error ? error.message : String(error));
    }
  }

  async verifyCall(callId: string): Promise<any> {
    const record = await this.repository.findByCallId?.(callId);
    if (!record) return { verified: false, status: 'NOT_ANCHORED' satisfies AuditState };
    if (!this.blockchain.enabled || !this.blockchain.get) return { verified: false, status: 'NOT_ANCHORED' satisfies AuditState, audit: record };
    const snapshot = await this.repository.getSnapshot(record);
    const material = materialize(record, snapshot);
    const onChain = await this.blockchain.get(record.evidence_id);
    const audioHashMatch = material.audioHash === record.audio_hash;
    const evidenceHashMatch = material.evidenceHash === record.evidence_hash && onChain?.evidenceHash === record.evidence_hash;
    const verified = Boolean(audioHashMatch && evidenceHashMatch && onChain);
    const status: AuditState = verified ? 'VERIFIED' : 'MISMATCH';
    await this.repository.markVerification?.(record.id, status);
    return { verified, status, audio_hash_match: audioHashMatch, evidence_hash_match: evidenceHashMatch, transaction_hash: record.transaction_hash, block_number: record.block_number, network: record.blockchain_network, anchored_at: record.anchored_at };
  }
}
