#!/usr/bin/env node
/** DEV-ONLY: modifies one byte in the official WAV without touching the audit DB or blockchain. */
import { Client } from 'pg';
import fs from 'node:fs/promises';

const callId = process.argv[2];
if (!callId || process.env.NODE_ENV === 'production') {
  throw new Error('Usage: NODE_ENV=development tsx scripts/tamper-audit-evidence.ts <call-id> (never runs in production)');
}
const client = new Client({ connectionString: process.env.DATABASE_URL });
await client.connect();
const result = await client.query('SELECT recording_path FROM audit_records WHERE call_id = $1', [callId]);
await client.end();
if (!result.rowCount) throw new Error(`No audit record for call ${callId}`);
const file = result.rows[0].recording_path as string;
const bytes = await fs.readFile(file);
if (bytes.length < 45) throw new Error('Recording is too short to tamper safely');
bytes[44] ^= 0x01; // first PCM byte; no on-chain or database changes
await fs.writeFile(file, bytes);
console.log(`DEV TAMPER COMPLETE: altered one persisted WAV byte for ${callId}; blockchain proof was not changed.`);
