import fs from 'node:fs/promises';
import type { PrismaClient } from '@prisma/client';
import { canonicalizeEvidence, sha256Hex } from './hashing.js';

export class PrismaAuditRepository {
  constructor(private readonly prisma: PrismaClient) {}

  async createForCompletedCall(callId: string, recording: { path: string; format: string }, stream: { sampleRate: number; channels: number; encoding: string }) {
    return this.prisma.audit_records.upsert({
      where: { call_id: callId },
      create: { call_id: callId, recording_path: recording.path, recording_format: recording.format, sample_rate_hz: stream.sampleRate, channels: stream.channels, bit_depth: stream.encoding === 'pcm_f32le' ? 32 : 16 },
      update: {},
    });
  }

  async getPending(id: string) {
    return this.prisma.audit_records.findFirst({ where: { id, state: { in: ['PENDING', 'FAILED'] } } });
  }

  async findByCallId(callId: string) { return this.prisma.audit_records.findUnique({ where: { call_id: callId } }); }

  async getSnapshot(record: any) {
    const call = await this.prisma.calls.findUnique({
      where: { id: record.call_id },
      include: { audio_chunks: { include: { ml_results: { select: { model_name: true, model_version: true } } } } },
    });
    if (!call) throw new Error('Call no longer exists');
    if (call.audio_chunks.some(chunk => chunk.processing_progress !== 'completed' || chunk.ml_results.length === 0)) {
      throw new Error('Call inference is not finalized yet');
    }
    const audioBytes = await fs.readFile(record.recording_path);
    const models = call.audio_chunks.flatMap(c => c.ml_results.map(r => ({ id: r.model_name, version: r.model_version }))).sort((a, b) => `${a.id}:${a.version}`.localeCompare(`${b.id}:${b.version}`));
    const risk = call.ai_likelihood_pct;
    if (risk === null || risk === undefined) throw new Error('Call has no final ML risk score yet');
    return {
      audioBytes,
      riskScore: risk.toFixed(4),
      verdict: risk >= 50 ? 'DEEPFAKE' : 'AUTHENTIC',
      modelId: 'voiceshield-fusion',
      modelVersion: `models@${sha256Hex(canonicalizeEvidence(models as any))}`,
      recordedAt: (call.ended_at ?? call.created_at).toISOString(),
      segmentStartMs: 0,
      segmentEndMs: call.duration_ms ?? 0,
    } as const;
  }

  async markSubmitted(id: string, data: { audioHash: string; evidenceHash: string; riskScore: string; verdict: string; modelId: string; modelVersion: string }) {
    await this.prisma.audit_records.update({ where: { id }, data: { state: 'SUBMITTED', audio_hash: data.audioHash, evidence_hash: data.evidenceHash, risk_score: data.riskScore, verdict: data.verdict, model_id: data.modelId, model_version: data.modelVersion, attempt_count: { increment: 1 }, last_error: null } });
  }

  async markConfirmed(id: string, proof: any) {
    await this.prisma.audit_records.update({ where: { id }, data: { state: 'CONFIRMED', audio_hash: proof.audioHash, evidence_hash: proof.evidenceHash, transaction_hash: proof.transactionHash, block_number: proof.blockNumber, blockchain_network: proof.network, contract_address: proof.contractAddress, anchored_at: proof.anchoredAt, next_attempt_at: null, last_error: null } });
  }

  async markFailed(id: string, error: string) {
    const row = await this.prisma.audit_records.findUnique({ where: { id } });
    const delayMs = Math.min(300_000, 5_000 * 2 ** Math.min(row?.attempt_count ?? 0, 6));
    await this.prisma.audit_records.update({ where: { id }, data: { state: 'FAILED', last_error: error.slice(0, 1000), next_attempt_at: new Date(Date.now() + delayMs) } });
  }

  async markNotAnchored(id: string) { await this.prisma.audit_records.update({ where: { id }, data: { state: 'NOT_ANCHORED' } }); }
  async markVerification(id: string, state: 'VERIFIED' | 'MISMATCH') { await this.prisma.audit_records.update({ where: { id }, data: { state } }); }
  async retryable(limit = 20) { return this.prisma.audit_records.findMany({ where: { state: { in: ['PENDING', 'FAILED'] }, OR: [{ next_attempt_at: null }, { next_attempt_at: { lte: new Date() } }] }, take: limit, orderBy: { created_at: 'asc' } }); }
}
