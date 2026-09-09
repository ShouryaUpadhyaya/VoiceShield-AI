# VoiceShield Blockchain Audit Trail

## Purpose
VoiceShield AI determines whether speech is likely synthetic. This audit trail answers a different question: **has the stored recording and the recorded AI result changed since it was anchored?** It is an integrity and chain-of-custody aid, not proof that a prediction is correct or that a microphone, caller, or device was trustworthy.

## Blockchain and hashes in plain language
A blockchain is an append-only ledger shared by nodes. Each block commits to prior block data, so altering historical data requires replacing accepted history under that network's consensus rules.

```text
Block 101: hash AAA
       |
Block 102: previous_hash AAA, hash BBB
       |
Block 103: previous_hash BBB, hash CCC
```

A smart contract is code running on that ledger. Blockchain is not magically unchangeable under every threat model: a compromised writer key, compromised validator majority, or local development chain reset changes the trust boundary.

SHA-256 is a one-way integrity fingerprint, not encryption:

```text
stored-call.wav -> SHA-256 -> e6ad7d...c6b8ad
```

It is deterministic, fixed length, and a one-byte change produces a different digest. A hash does not reveal the original audio, but a predictable input can still be guessed and checked; this is why VoiceShield anchors only hashes and opaque IDs.

## Implemented hybrid architecture

```text
CallVault / SIP PCM -> Media Gateway -> ML service
                         |              |
                         |              +--> final score/verdict
                         v
                persisted exact WAV + PostgreSQL Call
                         |
                         v
              AuditRecord outbox (non-blocking)
                         |
     RFC 8785 canonical evidence JSON + SHA-256
                         |
                         v
       EvidenceAnchor.sol on local Hardhat EVM ledger
                         |
                         v
 Dashboard: normal WAV playback + Verify Integrity
```

Audio, transcripts, identity, phone numbers, raw chunks, and sensitive call metadata remain off-chain. PostgreSQL remains the source for queries, playback references, users, and application state. The EVM ledger contains only a keccak-derived opaque evidence ID, SHA-256 evidence hash, and ledger timestamp.

## Design and technology choices

MVP uses a local Hardhat EVM JSON-RPC chain on port 8545, Solidity 0.8.24, OpenZeppelin `AccessControl`, ethers v6, Node `crypto` SHA-256, and RFC 8785/JCS through `json-canonicalize`. The minimal contract stores a mapping plus an `EvidenceAnchored` event. Only `WRITER_ROLE` can append; duplicate evidence IDs revert. There are no tokens, NFTs, or audio bytes on-chain.

A local chain is ideal for the SIH demo: offline, reproducible, visually understandable transaction hashes, and EVM migration compatibility. Public chains introduce cost/privacy/latency. Hyperledger Fabric or private Besu is a stronger production option for known institutional validators, but is too operationally heavy for this MVP. At high volume, batch evidence hashes into a Merkle root and periodically anchor it; this reduces transactions while retaining per-record proofs.

## Canonical evidence commitment

One finalized `Call` receives at most one `audit_records` row. The app does not invent a separate incident table because the existing persisted evidence unit is Call + recording + ML results.

The canonical `voiceshield.audit.evidence.v1` payload commits to:

- opaque evidence UUID and internal call UUID
- SHA-256 of exact final stored WAV bytes, including its header
- final score represented as decimal text
- derived `DEEPFAKE`/`AUTHENTIC` verdict
- `voiceshield-fusion` plus hash of sorted detector model/version list
- call-level segment `[0, duration_ms]`
- recording timestamp and audio representation (WAV, PCM S16LE, rate, channels, bit depth)

Never normalize, decode, resample, or re-encode before audio hashing. A sonically identical transformed WAV has different bytes and should fail this evidence check.

## Database schema
`audit_records` has one unique `call_id`, a unique opaque `evidence_id`, lifecycle `state`, stored recording representation, evidence/audio hashes, committed score/verdict/model fingerprint, transaction/block/network/contract proof, retry data, and timestamps. Migration: `media-gateway/prisma/migrations/20260909171500_add_audit_records/migration.sql`.

States: `PENDING`, `SUBMITTED`, `CONFIRMED`, `FAILED`, `VERIFIED`, `MISMATCH`, and `NOT_ANCHORED`. Existing calls have no row and the API reports `NOT_ANCHORED`; they remain readable and playable.

## Runtime flow and failure handling
The gateway persists the completed call/WAV first. It then creates an audit row and schedules an outbox job detached from the real-time audio/ML loop. RPC failure records `FAILED` and exponential retry time; it never fails streaming, WAV persistence, or detector inference. The outbox retries due `PENDING`/`FAILED` rows every 15 seconds. A mismatch is never re-anchored automatically.

For local development only, `BLOCKCHAIN_LOCAL_UNSAFE_RPC_SIGNER=true` uses a Hardhat unlocked account. Production must provide `BLOCKCHAIN_PRIVATE_KEY` from secret management; never expose it to browser/mobile code, `.env.example`, git, or logs.

## API and dashboard

- `GET /api/calls/:id/audit` returns audit proof or `NOT_ANCHORED`.
- `GET /api/calls/:id/verify` re-reads exact WAV bytes, reconstructs canonical current metadata, reads the contract, and reports `VERIFIED` or `MISMATCH`.
- `POST /api/calls/:id/audit/retry` runs an eligible outbox retry.
- Call details retain the existing `/api/calls/:id/recording` WAV stream. The Audit Integrity card shows status, evidence hash, transaction/block/network, and a Verify Integrity action.

`Blockchain Verified` means the current stored evidence and committed result match the anchored fingerprint. It does **not** mean blockchain agrees with the AI’s deepfake judgment.

## Local runbook

Terminal 1 (do not run `npm run fake-ml`):

```bash
cd /home/aayushdwivedi/Projects/VoiceShield-AI
PYTHONPATH=. .venv/bin/python -m ml.server.main
```

Terminal 2:

```bash
cd audit-chain
npm run node
npm run deploy:local
```

Terminal 3, set the printed contract address and use an uncommitted server-side key in real deployments:

```bash
cd media-gateway
DATABASE_URL='postgresql://postgres:voiceshield@localhost:15432/voiceshield' \
BLOCKCHAIN_ENABLED=true BLOCKCHAIN_RPC_URL=http://127.0.0.1:8545 \
BLOCKCHAIN_NETWORK='VoiceShield Local Chain' \
BLOCKCHAIN_CONTRACT_ADDRESS=0x... \
BLOCKCHAIN_LOCAL_UNSAFE_RPC_SIGNER=true BLOCKCHAIN_LOCAL_SIGNER_INDEX=1 \
npm run dev
```

Terminal 4: `cd frontend && npm run dev`. Open http://localhost:3000/calls.

## SIH demo (2–3 minutes)

1. Start the four services above.
2. Generate or receive a call. For a reproducible synthetic pipeline: `cd media-gateway && npm run send-test -- --duration 10 --source blockchain-e2e`.
3. Open the call, play the WAV normally, and show the AI score.
4. Show Audit Integrity: evidence hash, EVM transaction, block, and `CONFIRMED`.
5. Click Verify Integrity: `✓ Blockchain Verified`.
6. Development only, alter the stored evidence without changing the ledger:
   `DATABASE_URL=... npm run demo:tamper-audit -- <call-id>`.
7. Click Verify Integrity again: `✗ Integrity check failed: MISMATCH`.

The central explanation: “AI estimates whether speech is synthetic. The audio stays off-chain so it remains private and playable. VoiceShield anchors a fingerprint of that audio and result. If someone changes the WAV or committed decision later, verification detects the mismatch.”

## Threat model and security review

| Threat | Result |
|---|---|
| WAV modified after anchoring | Detectable: audio/evidence hash mismatch |
| committed score, verdict, model fingerprint modified | Detectable: canonical evidence mismatch |
| audit DB row deleted | Ledger still proves an opaque evidence commitment existed, but app association is lost |
| writer key stolen | Not fully protected; use KMS/HSM, rotation, least privilege, monitoring |
| fake audio captured before anchoring | Not protected |
| incorrect AI verdict | Not protected; blockchain does not improve classification accuracy |
| server compromised before anchoring | Limited protection; requires trusted capture/signing controls |
| private data placed on-chain | Prevented by contract/API design; review deployments and events |

Contract has no external value transfers or callbacks, limits writes to `WRITER_ROLE`, rejects zero/duplicate evidence values, and is append-only. EVM data is public to participants: do not add PII later. RPC should be private/network-restricted; the local node is demonstration-only. Database and chain commits are eventually consistent by design, handled by the persistent outbox rather than a distributed transaction.

## Production roadmap
Use a permissioned validator network for telecom/bank/cybercrime institutions, a KMS/HSM-backed signer with rotation, authenticated RPC, monitoring/alerts, durable job queue, independent archival verifier, multi-party custody signatures, and Merkle-root batching. Assess legal admissibility with counsel; an integrity check alone is not legal non-repudiation or proof of lawful collection.

## Sources
- RFC 8785 JCS: https://www.rfc-editor.org/rfc/rfc8785
- OpenZeppelin AccessControl: https://docs.openzeppelin.com/contracts/5.x/access-control
- Solidity security guidance: https://docs.soliditylang.org/en/latest/security-considerations.html
- ethers v6: https://docs.ethers.org/v6/
- Hardhat: https://hardhat.org/
- Hyperledger Fabric private data: https://hyperledger-fabric.readthedocs.io/en/release-2.2/private-data/private-data.html
