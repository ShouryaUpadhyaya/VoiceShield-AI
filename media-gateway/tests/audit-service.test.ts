import { describe, expect, it, vi } from 'vitest';
import { AuditService } from '../src/audit/service.js';

const baseRecord = {
  id: 'audit-1', call_id: 'call-1', evidence_id: 'c8da36da-ce6b-4aa6-a1ef-5b0f318eb2ef',
  state: 'PENDING', attempt_count: 0, recording_path: '/tmp/evidence.wav',
  recording_format: 'wav', sample_rate_hz: 48000, channels: 1, bit_depth: 16,
  created_at: new Date('2026-09-09T10:00:00.000Z'),
};

describe('AuditService', () => {
  it('anchors a finalized call asynchronously and persists its transaction proof', async () => {
    const repository = { getPending: vi.fn().mockResolvedValue(baseRecord), getSnapshot: vi.fn().mockResolvedValue({
      audioBytes: Buffer.from('official WAV bytes'), riskScore: '94.21', verdict: 'DEEPFAKE',
      modelId: 'voiceshield-fusion', modelVersion: 'pipeline@abc123', recordedAt: '2026-09-09T10:00:00.000Z',
    }), markSubmitted: vi.fn(), markConfirmed: vi.fn(), markFailed: vi.fn() };
    const blockchain = { enabled: true, anchor: vi.fn().mockResolvedValue({ transactionHash: '0xabc', blockNumber: 7, network: 'VoiceShield Local Chain', contractAddress: '0xcontract', anchoredAt: new Date('2026-09-09T10:00:01.000Z') }) };
    const service = new AuditService(repository as any, blockchain as any);

    await service.process('audit-1');

    expect(blockchain.anchor).toHaveBeenCalledOnce();
    expect(repository.markConfirmed).toHaveBeenCalledWith('audit-1', expect.objectContaining({ transactionHash: '0xabc', blockNumber: 7 }));
  });

  it('leaves an auditable failed state when blockchain submission fails', async () => {
    const repository = { getPending: vi.fn().mockResolvedValue(baseRecord), getSnapshot: vi.fn().mockResolvedValue({
      audioBytes: Buffer.from('official WAV bytes'), riskScore: '94.21', verdict: 'DEEPFAKE', modelId: 'voiceshield-fusion', modelVersion: 'pipeline@abc123', recordedAt: '2026-09-09T10:00:00.000Z',
    }), markSubmitted: vi.fn(), markConfirmed: vi.fn(), markFailed: vi.fn() };
    const service = new AuditService(repository as any, { enabled: true, anchor: vi.fn().mockRejectedValue(new Error('RPC unavailable')) } as any);

    await service.process('audit-1');

    expect(repository.markFailed).toHaveBeenCalledWith('audit-1', expect.stringContaining('RPC unavailable'));
  });

  it('reports NOT_ANCHORED for calls created before audit support', async () => {
    const service = new AuditService({ findByCallId: vi.fn().mockResolvedValue(null) } as any, { enabled: true } as any);
    await expect(service.verifyCall('legacy-call')).resolves.toMatchObject({ status: 'NOT_ANCHORED', verified: false });
  });
});
