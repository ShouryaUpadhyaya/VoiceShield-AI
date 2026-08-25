# VoiceShield AI — Project Status

**Last updated:** 2026-08-25
**Branch:** `main`
**Purpose of this document:** an unvarnished account of what exists, what is
claimed, what is not built, and where the project would fail if examined
closely. It is written to be useful to whoever picks this up next, including
future us.

*Recent Merges:* Integrated the `Dhwani` ONNX deepfake detector, the new real-time React Security Dashboard with WebSockets, and the Telephony/Media Gateway. The experimental remote streaming bridge (`ariktadas144/feat/ml-detection-pipeline`) has been compared but kept separate pending conflict resolution with the new gateway architecture.

---

## 1. Executive summary

VoiceShield AI detects AI-cloned voices on live calls and drives a risk-scoring
and prevention workflow.

**Where we actually are:** the deepfake detection signal is now a real, trained
model with a verified evaluation harness. The other three signals feeding the
risk engine — speaker verification, prosody, and call context — are still
placeholders. The system is a working single-signal detector wearing the
architecture of a four-signal one.

**The single most important caveat:** we do not yet have an out-of-domain
number. Every score quoted below is in-domain and therefore optimistic. The
literature is unambiguous that detectors at sub-1% in-domain EER can degrade
up to twentyfold out of domain. Until the ASVspoof 2021 DF evaluation runs, we
should quote no accuracy claim publicly.

---

## 2. What the project was before this work

Worth recording, because it frames everything else.

The repository had a complete-looking directory tree — `ml/`, `docs/`,
`tests/`, `infrastructure/` — in which **every file was 0 bytes**. The working
code was 18 files totalling a few kilobytes.

The deepfake "model" was:

```python
def analyze_deepfake(filename: str, audio_bytes: bytes) -> float:
    if 'fake' in filename.lower():
        return round(random.uniform(0.75, 0.99), 2)
```

The uploaded audio was read into memory and discarded. The percentage shown in
the UI was a random number keyed off the filename. The same pattern backed the
speaker and prosody services.

What was genuinely good and has been kept: the API contract, the six-stage
analysis flow, the weighted risk-fusion engine, the rule-based prevention
engine, and the React upload UI.

---

## 3. Current state, component by component

| Component | State | Evidence |
|---|---|---|
| Shared audio front-end | **Done, tested** | 48 unit tests; wav/mp3/m4a converge within 0.5 dB |
| ASVspoof 2019 data pipeline | **Done, verified** | Exact official counts, attacks, speakers; zero integrity issues |
| Silence-leak analysis | **Done, measured** | 34.8% / 33.1% silence-only EER across 50k utterances |
| Telephony codec augmentation | **Done, verified** | 7 codecs; AMR-NB moves spectral centroid 794→296 Hz |
| MGD phase features | **Done, tested** | 75% more phase-sensitive than LFCC on a magnitude-preserved twin |
| Detection metrics | **Done, validated** | Reproduces all 4 official ASVspoof 2021 baselines exactly |
| SSL model (WavLM + ASP) | **Trained** | dev EER 0.49% — in-domain, see caveats |
| Fusion model (SSL + LFCC/MGD) | **Training** | variable-length 2–4 s |
| ASVspoof 2021 eval harness | **Code done, data downloading** | baselines already recomputed from keys |
| FastAPI backend | **Wired to real model** | Dhwani ONNX pipeline, window pooling, calibrated output, 503 on missing model |
| Speaker verification | **Placeholder** | `random.uniform()`, labelled in `signal_provenance` |
| Prosody analysis | **Placeholder** | `random.uniform()`, labelled in `signal_provenance` |
| Call-context risk | **Placeholder** | substring match on the filename |
| Risk fusion + prevention | **Real logic** | deterministic weighted fusion, rule-based actions |
| React frontend | **Done, dashboard** | Live security dashboard, real-time WS client, risk gauge, waveform |
| Database / persistence | **Not started** | all model files 0 bytes |
| Streaming (WebSocket/gRPC) | **Implemented** | Telephony/Media gateway pipeline, SSE logging |
| Auth / DPDP compliance | **Not started** | — |

### 3.1 Verified findings

These are measurements, not assumptions, and each drove a design decision.

**The ASVspoof silence shortcut is real.** Across all 25,380 train and 24,844
dev utterances:

| | bonafide | spoof |
|---|---|---|
| mean edge silence | 1.06 s (train) / 1.31 s (dev) | 0.81 s |
| mean silence fraction | 31.3% / 37.1% | 23.3% |
| silence-only EER | **34.8% / 33.1%** | (chance = 50%) |
| duration-only EER | 48.9% / 48.2% | (i.e. chance) |

Silence duration alone separates the classes well above chance while total
duration does not, so the signal is specifically the silence. Per attack the
mean ranges from 0.17 s (A01) to 1.53 s (A02) — a model could partly identify
the *synthesis system* from silence. Hence `trim_edges` is the default.

**Our EER implementation is correct.** Recomputed from the ASVspoof 2021 keys
package's own baseline score files:

| baseline | ours | published |
|---|---|---|
| LFCC-GMM | 25.25% | 25.25% |
| CQCC-GMM | 25.56% | 25.56% |
| LFCC-LCNN | 23.48% | 23.48% |
| RawNet2 | **22.38%** | **22.38%** |

Exact on all four. This also fixed the protocol: published numbers use
`phase == "eval"` (533,928 of 611,829 trials).

**MGD captures what LFCC cannot.** Against a twin with an exactly preserved
magnitude spectrum but randomised phase, MGD shifts 0.538 vs LFCC's 0.308.

**Hardware characterisation (GTX 1650, 4 GB, 12 cores):**

| config | throughput | peak VRAM | epoch |
|---|---|---|---|
| SSL bs=32 @4.04s | 25.4 utt/s | 1.96 GiB | 16.6 min |
| SSL bs=64 | OOM | — | — |
| **fusion bs=24 @4.04s** | 20.6 utt/s | 2.12 GiB | 20.5 min |
| fusion bs=24 @2.00s | 42.7 utt/s | 1.24 GiB | — |
| SSL bs=32 **with fp16** | **5.8 utt/s** | 2.36 GiB | 72.6 min |

**fp16 is 4× slower here.** The GTX 1650's TU117 die has no tensor cores, so
autocast pays conversion overhead for no compute benefit. Mixed precision is
deliberately disabled; do not "optimise" it back on.

---

## 4. Where this project fails

Ordered by how badly it would hurt under scrutiny.

### 4.1 Critical — the product claim outruns the implementation

**F1. Two of four risk signals are random numbers.**
`speaker_service.verify_speaker()` and `prosody_service.analyze_prosody()` still
return `random.uniform()` keyed off the filename. In the fusion weights those
signals carry **0.25 + 0.15 = 40%** of the risk score. A fifth (`context_risk`,
weight 0.20) is a substring check for `"transfer"` in the filename. So **60% of
the displayed risk score is not a measurement.**

The API now labels this in `signal_provenance`, so it is disclosed rather than
hidden — but the number on the dashboard is still 60% noise.

**F2. No real-time path exists.** The product is pitched as live-call detection
with sub-2 s alerting. The implementation is a REST file-upload endpoint. There
is no WebSocket or gRPC streaming, no VAD-driven segmentation, no FreeSWITCH or
Twilio integration, and no session state. The "real-time" claim is currently
unsupported by any code.

**F3. No out-of-domain evaluation yet.** The only numbers we have are in-domain
(train and dev share attacks A01–A06). This is precisely the configuration the
literature warns produces flattering, meaningless scores.

**F4. Concurrency is 1.** The predictor serialises GPU access behind a
`threading.Lock` because a 4 GB card cannot safely serve concurrent requests.
The blueprint targets 1,200–1,500 concurrent calls per node. We are roughly
three orders of magnitude short, and nothing in the current design closes that
gap — it needs ONNX/TensorRT export and a batching inference server.

### 4.2 Serious — methodological risk

**F5. Only 20 training speakers.** ASVspoof 2019 LA train contains 20 speakers.
Research on the Identity Sensitivity Score shows detectors frequently learn
speaker identity rather than synthesis artefacts, and fail on unknown speakers.
We have implemented **no** mitigation — no Reference-Augmented Training, no hard-
sample mining, no identity-adversarial objective. If the 2021 DF number comes
back poor, this is the most likely cause.

**F6. Codec augmentation has fixed diversity.** Each training utterance is
rendered through exactly one randomly chosen codec, fixed for the whole run.
Online augmentation would vary it every epoch; we traded that away for GPU
throughput. The model sees 7 codec types but only one realisation per utterance.

**F7. Calibration is single-condition.** Temperature is fitted on clean dev
audio. Codec-degraded audio very likely needs a different temperature, so the
probability shown for a real phone call may be miscalibrated even if the
ranking is fine.

**F8. Window pooling is an untuned heuristic.** The 90th percentile over
windows was chosen by reasoning, not measurement. It has not been compared
against max, mean, or a learned aggregator.

**F9. No adversarial evaluation.** `tests/adversarial/` — codec attack, replay,
noise, unseen models — are all still 0-byte stubs.

**F10. No fairness or bias evaluation.** The blueprint explicitly flags severe
degradation on South Asian speakers in Western-trained systems. We have not
measured false-alarm rate by gender or accent. Our Indic robustness argument
rests entirely on MGD being theoretically language-agnostic — a reasonable
argument, but **not a measurement**.

**F11. min t-DCF is CM-only.** Without the official ASV scores it is not the
challenge metric, and is labelled as such. Do not quote it as t-DCF.

### 4.3 Engineering and compliance gaps

**F12. No authentication, and CORS is wide open.** `allow_origins=["*"]`,
`backend/app/core/security.py` is empty. For a service processing voice
biometrics this is unacceptable outside a demo.

**F13. No DPDP compliance implementation.** The Act treats voice data used for
identification as sensitive personal data, with penalties up to ₹250 crore.
Nothing is implemented: no consent capture, no explicit raw-audio destruction,
no feature-only retention, no TLS enforcement, no audit logging. The design is
described in `infrastructure/security/*` — those files are also empty.

**F14. No persistence at all.** Every file under `backend/app/models/` and
`backend/app/database/` is 0 bytes. There is no incident history, no speaker
enrolment store, no call record. The dashboard has nothing to read.

**F15. No CI.** Tests run only when someone remembers. No GitHub Actions, no
pre-commit, no coverage gate.

**F16. Frontend is a single file with a suspect import.** `App.tsx` imports
`Waveform` from `lucide-react`, which I believe does not export that name
(it is `AudioWaveform`). Unverified — `node_modules` has never been installed
in this working copy. The `pages/` and `components/` trees are 0-byte stubs.

**F17. Training data comes from a third-party mirror.** We use a HuggingFace
parquet mirror because Edinburgh DataShare served at ~50 KB/s. This is mitigated
by hard integrity gates (exact counts, class balance, speaker counts, attack
inventory, and cross-checking `system_id` against the label column) but remains
a supply-chain dependency worth stating.

**F18. No model registry.** The predictor picks a checkpoint by `mtime` glob.
There is no versioning, no promotion process, no rollback.

---

## 5. Plan

### 5.1 Immediate (in flight or next)

1. **Finish fusion training** and evaluate on ASVspoof 2019 eval (unseen
   attacks A07–A19) and **ASVspoof 2021 DF** (nine codec conditions). Report
   against RawNet2's 22.38%. *This is the gate on every accuracy claim.*
2. **Measure RTF and end-to-end latency** against the SLA table
   (RTF ≤ 0.1, E2E < 500 ms). Cheap, and it decides whether frozen WavLM is
   viable for streaming or whether RawNet2 is needed for the MVP path.
3. **Report FAR/FRR by name** against the < 1.5% / < 3.0% targets, at both
   4.04 s and 2.0 s windows.

### 5.2 Short term — kill the mocks

4. **Real prosody** (F1): jitter, shimmer, HNR, F0 trajectory smoothness,
   formant plausibility. CPU-only, no training required.
5. **ECAPA-TDNN speaker verification** (F1): pretrained via SpeechBrain,
   192-dim embeddings, cosine similarity now and PLDA later, plus an enrolment
   store. No training required.
6. **SASV fusion check**: verify that a perfect ASV match cannot rescue a call
   the detector flags as synthetic.
7. **Silero VAD** replacing the energy-threshold trim — better on noisy
   telephony and a prerequisite for streaming segmentation.

### 5.3 Medium term — make the real-time claim true

8. **WebSocket streaming path**: 2 s window / 100 ms hop, session state,
   continuous risk updates.
9. **ONNX export** and a batching inference server (F4).
10. **Persistence** (F14): incidents, speaker profiles, call records.
11. **Auth + DPDP basics** (F12, F13): API keys, CORS lockdown, consent flag,
    explicit raw-audio destruction, feature-only retention.
12. **CI** (F15): run the 48 tests on every push.

### 5.4 Research track — close the methodological gaps

13. **Identity-shortcut mitigation** (F5): Reference-Augmented Training and
    hard-sample mining.
14. **Adversarial test suite** (F9): fill in the four stub files.
15. **Indic evaluation** (F10): measure false-alarm rate on genuine Indian
    speech (IndicVoices/Kathbath), then consider training on IndieFake. The
    `use_mgd` / `use_lfcc` config flags mean this is an ablation, not a rewrite.
16. **Per-codec calibration** (F7).

---

## 6. What we would improve if we started again

- **Build the evaluation harness before the model.** Validating our EER against
  the published baselines took under an hour and paid for itself immediately;
  doing it first would have removed all doubt about every number after.
- **Measure the shortcut before choosing the preprocessing.** The silence-leak
  measurement changed a default from a guess to a decision. The same question
  should be asked of every preprocessing step.
- **Do not scaffold empty directories.** The 0-byte tree made the project look
  far more complete than it was, to the point where "the preprocessing is left"
  was a reasonable but wrong description of the remaining work.
- **Pick the serving window before training.** The 4 s vs 2 s conflict cost a
  full retrain and was knowable on day one from the latency requirement.

---

## 7. How to reproduce

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv --index-url https://download.pytorch.org/whl/cu126 \
    -r ml/requirements-torch.txt
uv pip install --python .venv -r ml/requirements.txt

./ml/data/download_asvspoof.sh                       # ~7.5 GB, resumable
PYTHONPATH=. .venv/bin/python ml/data/build_cache.py --splits train dev
PYTHONPATH=. .venv/bin/python -c \
    "from ml.data.build_cache import build_codec_variant; build_codec_variant('train')"
PYTHONPATH=. .venv/bin/python ml/deepfake_detection/training/train.py

./ml/data/download_asvspoof2021.sh                   # eval only, never trained on
PYTHONPATH=. .venv/bin/python ml/data/build_asvspoof2021.py --track DF --baselines-only
PYTHONPATH=. .venv/bin/python -m pytest tests/unit -q
```

Related reading: `docs/research/preprocessing.md` (pipeline decisions and the
measurements behind them) and `docs/research/evaluation_protocol.md` (why we
never train on 2021, and how the metrics were validated).
