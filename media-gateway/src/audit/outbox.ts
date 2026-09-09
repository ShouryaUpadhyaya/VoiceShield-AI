import { EvmEvidenceClient } from './blockchain-client.js';
import { PrismaAuditRepository } from './repository.js';
import { AuditService } from './service.js';
import type { PrismaClient } from '@prisma/client';
import { logger } from '../logger.js';

export class AuditOutbox {
  private readonly repository: PrismaAuditRepository;
  private readonly service: AuditService;
  private timer?: ReturnType<typeof setInterval>;

  constructor(prisma: PrismaClient) {
    this.repository = new PrismaAuditRepository(prisma);
    this.service = new AuditService(this.repository, new EvmEvidenceClient());
  }

  start(): void {
    if (this.timer) return;
    this.timer = setInterval(() => void this.retryDue(), 15_000);
    void this.retryDue();
  }

  stop(): void { if (this.timer) clearInterval(this.timer); this.timer = undefined; }
  async enqueue(id: string): Promise<void> { setImmediate(() => void this.run(id)); }
  async run(id: string): Promise<void> { await this.service.process(id); }
  async retryDue(): Promise<void> {
    for (const record of await this.repository.retryable()) await this.run(record.id);
  }
  async verifyCall(callId: string): Promise<any> { return this.service.verifyCall(callId); }
  async getByCall(callId: string): Promise<any> { return this.repository.findByCallId(callId); }

  async createForCompletedCall(callId: string, recording: { path: string; format: string }, stream: { sampleRate: number; channels: number; encoding: string }): Promise<void> {
    try {
      const record = await this.repository.createForCompletedCall(callId, recording, stream);
      await this.enqueue(record.id);
    } catch (error) {
      logger.error('AUDIT_CREATE_ERROR', { callId, error: String(error) });
    }
  }
}
