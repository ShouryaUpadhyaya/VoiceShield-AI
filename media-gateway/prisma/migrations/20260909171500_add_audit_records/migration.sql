-- VoiceShield blockchain-backed audit records. Audio remains in recordings/storage.
CREATE TABLE "audit_records" (
  "id" TEXT NOT NULL,
  "call_id" TEXT NOT NULL,
  "evidence_id" TEXT NOT NULL,
  "state" TEXT NOT NULL DEFAULT 'PENDING',
  "recording_path" TEXT NOT NULL,
  "recording_format" TEXT NOT NULL,
  "sample_rate_hz" INTEGER NOT NULL,
  "channels" INTEGER NOT NULL,
  "bit_depth" INTEGER NOT NULL,
  "audio_hash" TEXT,
  "evidence_hash" TEXT,
  "risk_score" TEXT,
  "verdict" TEXT,
  "model_id" TEXT,
  "model_version" TEXT,
  "transaction_hash" TEXT,
  "block_number" INTEGER,
  "blockchain_network" TEXT,
  "contract_address" TEXT,
  "anchored_at" TIMESTAMP(3),
  "last_error" TEXT,
  "attempt_count" INTEGER NOT NULL DEFAULT 0,
  "next_attempt_at" TIMESTAMP(3),
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "audit_records_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "audit_records_call_id_key" ON "audit_records"("call_id");
CREATE UNIQUE INDEX "audit_records_evidence_id_key" ON "audit_records"("evidence_id");
ALTER TABLE "audit_records" ADD CONSTRAINT "audit_records_call_id_fkey"
  FOREIGN KEY ("call_id") REFERENCES "calls"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
