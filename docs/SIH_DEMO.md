# SIH demo runbook

Use the [model audit](research/SIH_MODEL_AUDIT.md) as the evidence and limitations sheet. The demo outputs a synthetic-audio evidence index, not a probability of fraud.

## Provision once, then rehearse offline

From the repository root, use Python 3.11 and the installed matching Torch/Torchaudio environment:

```bash
source .venv/bin/activate
pip install -r ml/requirements.txt -r backend/requirements.txt python-dotenv
```

Provision `data/external_models/dhwani/best_model.onnx`, `ml/artifacts/fusion_mgd_varlen_v1/best.pt`, and `ml/deepfake_detection/indic/frozen/voiceshield-indic-iv15.pth`. These are large local artifacts and are not included by a normal git clone. Preserve the WavLM encoder's Hugging Face cache, which model construction needs. Do not promise that `git lfs pull` provisions this repository: weights are gitignored here.

The missing ECAPA package and weights were restored in the audited workspace. To reproduce the download elsewhere:

```bash
hf download speechbrain/spkrec-ecapa-voxceleb embedding_model.ckpt mean_var_norm_emb.ckpt classifier.ckpt label_encoder.txt --local-dir models/ecapa
```

The tracked `models/ecapa/hyperparams.yaml` is also needed. Never reuse an unverified enrollment gallery as proof of identity.

Inspect `ml/.env.example`. Retire the old prosody=0.15 configuration: startup now rejects it. Defaults select iv15 for scoring and run Dhwani/custom/prosody/ECAPA as diagnostic outputs. Explicit checkpoint environment variables are documented in that example. Invalid explicit paths do not silently select another checkpoint.

Start the ML service from the root in one terminal:

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 python -m ml.server.main
```

Check `http://localhost:8011/ready`, `/api/models` and `/api/config/fusion`. All five adapter states should be available for the full demo. Readiness is not an accuracy certificate. There is one model process; use one worker on limited memory.

Start the configured PostgreSQL instance, then follow the media gateway's setup for its own database and Prisma schema. In separate terminals:

```bash
cd media-gateway
npm run dev
```

```bash
cd frontend
npm run dev
```

Use the existing gateway `.env.example` to set the correct database and ML address. Do not run integration tests that clear tables against recorded user calls. The audit did not reset or provision the user's database.

## Five-minute judging flow

1. Show loaded model versions, the provisional weights and the meaning of `/100`.
2. Upload a consented labeled genuine sample and a synthetic sample. Show each detector's output and the final evidence status, including disagreement.
3. Upload silence: expect unknown/insufficient evidence, not 0% fraud. Show a quiet or clipped example and explain abstention/review.
4. Upload a recording up to 60 seconds: inspect its three-second window outputs, mean and peak. A mean can dilute a brief synthetic interval; the timeline is evidence, not proof that the rest of the call is genuine.
5. Stream a consented file using the existing simulator through the gateway, then inspect the recorded call. Show what happens when the primary model is unavailable: no final score. A physical CallVault call still needs a device rehearsal.
6. Close with the audit comparison and explain why Stage A/Spectra is the next candidate upgrade, and why unseen generators remain a release gate.

## Reproduce the audits

The optional corpus path below points to the research checkout present on the audited machine. Supply an equivalent path elsewhere; its manifests and audio are not bundled with this repository.

```bash
python scripts/audit_models.py historical --corpus-root /path/to/voiceshield --out /tmp/historical_audit.json
HF_HUB_OFFLINE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 python scripts/audit_models.py live --corpus-root /path/to/voiceshield --per-group 3 --out /tmp/live_audit.json
HF_HUB_OFFLINE=1 python scripts/audit_research_candidates.py --corpus-root /path/to/voiceshield --live-report /tmp/live_audit.json --out /tmp/candidate_audit.json
HF_HUB_OFFLINE=1 python scripts/audit_checkpoint_variants.py --corpus-root /path/to/voiceshield --out /tmp/checkpoint_audit.json
python scripts/validate_ml_service.py --corpus-root /path/to/voiceshield --out /tmp/service_smoke.json
```

## Verification

Recorded result: 80 Python tests, 61 selected gateway tests, 9 frontend tests and both builds passed. Real-model HTTP/WebSocket smoke checks also passed. Reports are in `docs/research/validation/`.

```bash
python -m pytest ml/tests tests/unit -q
```

```bash
cd media-gateway
npm run build
npm test -- tests/risk-summary.test.ts tests/persistence-risk.test.ts tests/protocol.test.ts tests/recorder.test.ts tests/session.test.ts tests/chunker.test.ts tests/lan.test.ts tests/api.test.ts
```

```bash
cd frontend
npm test
npm run build -- --webpack
```

In the audit environment, the sandbox blocked local networking and the FastAPI test client's asynchronous wake-up; those tests and the production build succeeded outside that sandbox. Database-backed E2E tests remain a separate gate requiring a disposable test database. Dependency deprecation warnings are recorded, not counted as validation failures.
