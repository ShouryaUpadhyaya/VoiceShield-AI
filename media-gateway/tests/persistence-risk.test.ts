import { it, expect, vi } from 'vitest';

const db = vi.hoisted(() => ({
  calls: { findFirst: vi.fn().mockResolvedValue({ id: 'call', status: 'COMPLETED' }), update: vi.fn().mockResolvedValue({}) },
  audio_chunks: { findUnique: vi.fn().mockResolvedValue({ id: 'chunk' }), findMany: vi.fn().mockResolvedValue([{ id: 'chunk' }]), update: vi.fn().mockResolvedValue({}) },
  ml_results: { create: vi.fn().mockResolvedValue({}), findMany: vi.fn().mockResolvedValue([
    { result_json: { signals: { deepfake_probability: .8 } } },
    { result_json: { signals: { deepfake_probability: null } } },
  ]) },
}));
vi.mock('@prisma/client', () => ({ PrismaClient: class { constructor() { return db; } } }));
vi.mock('pg', () => ({ Pool: class {} }));
vi.mock('@prisma/adapter-pg', () => ({ PrismaPg: class {} }));
import { persistMlResult } from '../src/persistence.js';

it('refreshes a completed call after a late score and preserves zero prosody', async () => {
  persistMlResult('session', 2, { signals: { deepfake_probability: .8, prosody_analysis: { overall_prosody_risk: 0 } } });
  await vi.waitFor(() => expect(db.calls.update).toHaveBeenCalledWith({ where: { id: 'call' }, data: { ai_likelihood_pct: 80 } }));
  expect(db.ml_results.create.mock.calls[0][0].data.anomaly_score).toBe(0);
});
