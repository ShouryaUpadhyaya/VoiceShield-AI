# VoiceShield model audit and SIH readiness

Audit date: 7 September 2026. Scope: the active `ml.server` → media gateway → Next.js path, local checkpoints, and research score files referenced by this repository. No recordings were uploaded or published.

## Decision

The application can present a tested **synthetic-audio evidence index**, with model outputs and abstention. It cannot presently provide a validated worldwide probability of fraud. Authentic speech can carry a scam; synthetic speech can be legitimate. No trained scam-content/context classifier or representative fraud-outcome dataset is connected to this pipeline.

For the integrated models, the provisional default is **Indic iv15 = 1; Dhwani = 0; custom WavLM = 0; prosody = 0**. All five adapters still run, and disagreement between valid deepfake detector outputs triggers review. This choice follows historical development EER, not external/test tuning: iv15 4.02%, original ensemble 4.46%, equal detector average 9.83%, custom 26.21%, Dhwani 46.92%. It is a provisional choice because those development scores used whole-clip processing; the live contract is three-second windows.

**Preferred upgrade candidate: Stage A / Spectra-AASIST.** Stage A has the lowest historical development EER among the available research candidates. Both candidates also performed well in fresh smoke inference. They remain in the sibling research checkout and are not integrated into the service. This is an outstanding detector-upgrade task, not a claimed completed deployment. Do not invent a mixture weight from the external results: validate a single strong model against learned fusion before adding weaker detectors.

## What actually ran

- Recomputed metrics from 12,231 joined historical records, with file hashes and separate checkpoint names. Core comparisons use 1,485 internal development clips, 1,490 internal test clips and 1,800 external clips. Other scored partitions are retained in the source files; these counts are not all training-independent trials.
- Ran all five active adapters on 87 deterministically selected labeled clips across language, label, split and internal/external strata, plus nine quality controls. One labeled clip was rejected by the quality gate, leaving 86 for detector metrics. No scores or labels were used to choose the clip within a stratum.
- Ran the two research candidates on those same 86 usable three-second excerpts, using their own preprocessing contract.
- Loaded the three local WavLM checkpoint variants and scored two development examples each as an architecture/loading check. Two examples cannot establish accuracy. `wavlm_asp_v1` and `ssl_4s_baseline` have **identical SHA-256 hashes** (`e7310f813ad7…`): they are duplicate checkpoints, not independent ensemble members. All three predict a low spoof score for the selected spoof example; compatibility is not correctness.

Evidence: [historical report](validation/historical_audit.json), [live outputs](validation/live_audit.json), [research candidate outputs](validation/candidate_audit.json), [checkpoint compatibility outputs](validation/checkpoint_audit.json). JSON reports contain the detailed predictions, operating thresholds where applicable, errors and latency. Reproduction commands are in [the demo runbook](../SIH_DEMO.md).

Final software checks: **80 Python tests, 61 selected gateway tests and 9 frontend tests passed**. Gateway TypeScript build and Next.js production build passed. A [real-model service smoke test](validation/service_smoke.json) passed HTTP single/multiwindow uploads and WebSocket audio with all five models loaded; it also confirmed finite 192-dimensional ECAPA embeddings and repeat-input cosine approximately 1.0. That is a functional check, not speaker-verification accuracy. Database-backed tests were not signed off; the selected persistence regression uses a mocked database.

The manifest contains 10,431 rows, **6,667 with unknown speaker identity**. Recorded content hashes do not overlap across its named splits, but this does not establish speaker independence, perceptual deduplication, generator independence, or absence from a pretrained model's training set. That gap prevents a strong generalization claim.

## Historical detector comparison

EER is an error rate, not accuracy or a deployment threshold. Lower is better. These values are recomputed with tie-aware ROC metrics; they can differ from older research code that sorts tied scores one example at a time.

| Detector / configuration | Dev EER | Internal test EER | External EER |
|---|---:|---:|---:|
| Indic v0.1, superseded | 25.69% | 2.42% | 47.50% |
| Indic iv15, current | 4.02% | 2.41% | 46.63% |
| Dhwani | 46.92% | 53.31% | 27.89% |
| Custom WavLM + LFCC/MGD | 26.21% | 25.74% | 55.75% |
| Prosody heuristic, diagnostic only | 41.68% | 47.86% | 71.10% |
| Original current ensemble, using iv15 | 4.46% | 2.41% | 43.00% |
| Equal mean of the three detectors | 9.83% | 6.97% | 28.12% |
| Stage A, research candidate | 0.28% | 0.54% | 0.38% |
| Spectra, research candidate | 1.31% | 1.34% | 0.25% |

The report additionally fixes a threshold using only genuine development scores at an empirical ≤5% false-positive rate, then measures test/external false alarms and misses. For iv15, that operating point produces **19.5% false alarms and 74.25% misses externally**. For the original current ensemble, the figures are **17.1% and 78.0%**. Good internal results do not transfer reliably.

Previous `research/final_eval.json` calls an ensemble “CURRENT”, but its `indic` column was generated with v0.1, not iv15. It also reports four restricted-language cross-domain cells; those should not be compared directly with the broader aggregate table above. The new report keeps `legacy_fusion` and `current_original_fusion` distinct.

## Fresh three-second smoke comparison

86 usable clips: 44 genuine and 42 spoof. These are small diagnostic samples, include development clips, and were already available locally. They are not a new blind validation dataset.

| Model | AUC | EER | False alarms at raw 0.5 | Misses at raw 0.5 |
|---|---:|---:|---:|---:|
| Indic iv15 | 0.9023 | 19.05% | 15.91% | 19.05% |
| Dhwani | 0.5731 | 43.18% | 56.82% | 28.57% |
| Custom WavLM fusion | 0.6442 | 38.10% | 38.64% | 38.10% |
| Prosody heuristic | 0.4232 | 52.27% | 22.73% | 95.24% |
| Spectra candidate | 0.9995 | 2.27% | Not calibrated | Not calibrated |
| Stage A candidate | 0.9995 | 2.27% | Not calibrated | Not calibrated |

Raw 0.5 is used only for a uniform diagnostic comparison. Indic carries its checkpoint's decision threshold; custom WavLM reports approximately 0.7368 after temperature scaling. The evidence index's review bands are a demo policy, not either model's fitted operating point.

All five active adapters completed without inference exceptions on usable inputs. CPU sequential pipeline latency was approximately 1.1 seconds median per three-second window in an isolated run; the exact report contains the latest p50/p95. Initialization and queue delay are additional. Live alerts therefore require the initial three seconds of audio plus inference and transport. This does not establish simultaneous-call capacity or GPU performance.

## Capabilities, contracts and limits

| Component | What it can do and how it is configured | What it cannot establish |
|---|---|---|
| Indic iv15 | Adapted RawNet2; mono 16 kHz; checkpoint-specific sample count, silence trimming, class index and threshold. Produces synthetic evidence and per-model verdict. Frozen checkpoint hash starts `171a70affd21`. | Worldwide generalization, scam intent, speaker identity, or reliable unseen voice-conversion detection. The extra multiclass head is not a validated attack-family classifier here. |
| Dhwani | XLS-R 300M + AASIST in ONNX; exactly 48,000 samples; mean/variance normalization; class 1 is synthetic. Local hash starts `d1c232bf4d79`. | Strong accuracy merely because an ONNX session loads; transcription, translation, or robustness to all accents/novel generators. The local smoke false-positive rate is high. |
| Custom fusion | WavLM-base-plus plus LFCC/MGD; 64,600-sample checkpoint front end, RMS normalization and temperature scaling; p90 pooling inside the predictor. Hash starts `ec4b02624199`. | The ASVspoof development result is not an Indian telephone-call result. Checkpoint temperature calibration does not transfer automatically to new data or a fused score. |
| WavLM ASP / SSL baseline checkpoints | Alternative saved `ssl` architectures; tested for loading and finite sample outputs, not active in the default pipeline. | They are not extra independent live votes. Shared encoders/training can make errors correlated. Their two-example checks are not an accuracy comparison. |
| Prosody | Praat/Parselmouth pitch, voicing, jitter, shimmer, HNR, pause and rate features with hand-chosen reference bounds. | Probability of synthesis, emotional intent, dishonesty, or diagnosis. Noise, atypical speech, language and recording differences can be anomalous for legitimate reasons. Zero fusion weight is enforced. |
| ECAPA-TDNN | 192-dimensional speaker embeddings; cosine comparison against a local enrollment gallery; provisioned SpeechBrain 1.0.3 and official weights. Reports gallery match status. | Anti-spoofing, liveness, caller-ID authentication, or verified identity. A nearest gallery match is identification, not verification of a claimed person. Enrollment provenance and same/different-speaker FAR/FRR are unvalidated; 0.75 is a heuristic cosine threshold. |
| Spectra / Stage A | Research XLS-R + AASIST candidates; preemphasis 0.97, no waveform normalization, repeat short audio to 64,600 samples; score column 1 is genuine evidence, so its sign is inverted for comparisons. Stage A replaces trained bridge/head weights. | A raw logit is not a probability. Strong historical and smoke results do not prove live telephony robustness or lack of training overlap. Service integration and calibrated thresholds are still required. |
| Quality gate | Rejects invalid arrays, nonfinite values, DC/silence, <1 second and too little active audio; flags clipping. | This is an energy/integrity gate, not a validated VAD. Noise can pass it; passing does not prove speech. Quiet speech can be rejected. |

The Dhwani preprocessing and class order match its [official model card](https://huggingface.co/ayush2635/Dhwani-Multilingual-Deepfake-Audio-Detection-Model). SpeechBrain specifies 16 kHz mono input for tensor inference and speaker comparison by cosine distance; its VoxCeleb results are not a guarantee for this corpus. [ECAPA model card](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb). Spectra's published contract, licensing and cross-dataset results are recorded in its [model card](https://huggingface.co/lab260/Spectra-AASIST); the local download record pins revision `eb65c2662d9e646d72557b3f4bdd08b000068c7f`.

## Repairs made

- Replaced arbitrary four-signal probability mixing with a versioned, explicit evidence policy; preserved supporting outputs and manual detector ablations. Invalid/negative/nonfinite/partial weight configurations are rejected. Prosody cannot be promoted to a standalone accusation.
- Added no-score/unknown handling, disagreement review, effective contribution weights and calibration status. No automatic financial blocking is authorized by the new score.
- Pinned artifact selection; removed modification-time selection and silent fallback from an invalid Indic override. Removed automatic v0.1 fallback. Artifact paths no longer depend on machine-specific symlinks, and custom/Dhwani versions include content hashes.
- Fixed Indic imports so generic `model`/`audio_utils` modules cannot shadow the intended implementation.
- Restored ECAPA dependencies and local weights, corrected offline pretrained paths, made enrollment resolution independent of working directory, and rejected malformed enrollment vectors.
- Added model loading to FastAPI lifespan; readiness requires a scoring detector, not just prosody. Serialized shared model execution and moved upload inference off the event loop.
- Aligned uploads to three-second windows (60-second upload cap); returned all window outputs, mean and peak evidence, and rejected windows. Preserved actual partial-window duration over the gateway.
- Excluded null/nonfinite results from call averages, preserved zero prosody and refreshed completed-call scores when late model results arrive.
- Fixed dashboard compile errors, raw-result storage, null rendering, misleading probability labels and simulator shell interpolation. The legacy backend remains separate and is explicitly excluded from this validated demo path.

## How to produce a defensible final probability

1. Fix the target: synthetic speech detection, claimed-speaker verification, and fraud are different outcomes. Use a synthetic-audio evidence score now; train a fraud model only when real fraud/outcome labels and contextual inputs exist.
2. Freeze model/code hashes and **the exact live window, codec, resampling and pooling contract**. Re-score development data through that contract. Whole-clip calibration must not silently be served on three-second chunks.
3. Split by original recording and speaker; keep transformed versions together. Hold out generators, sources and language/codec conditions. Unknown speaker metadata must be repaired or the independence limitation retained.
4. Within development data, compare the best single model, regularized logistic fusion of detector logits, and ablations. Generate out-of-fold base/calibration predictions for stacking. Exclude prosody and gallery mismatch unless held-out evidence shows a repeatable benefit for the chosen outcome. An ensemble is useful only if it improves the target operating point.
5. Fit final calibration on disjoint data. A calibrated log-likelihood ratio can be combined with an explicitly stated deployment prior: `P(synthetic | evidence) = sigmoid(LLR + logit(prior))`. Ordinary logistic posterior logits need the calibration prior removed before being called LLRs. The current app has neither that validated LLR nor a deployment prior. [BOSARIS](https://arxiv.org/abs/1304.2865), [scikit-learn calibration guidance](https://scikit-learn.org/stable/modules/calibration.html).
6. Choose low/review/high thresholds on development data using the acceptable false-accusation rate and miss cost. Freeze thresholds before testing. Report call-level false alarms/misses, confidence intervals, EER, AUC, Brier/log loss, reliability plots, abstention coverage, latency and per-language/generator performance. Calibrate call pooling separately; mean or p90 of calibrated chunk probabilities is not automatically a call probability.
7. Evaluate telephone bandwidth/codecs, replay, noise, quiet speech, mixed genuine/fake segments, unseen generators, multiple speakers and packet loss. The latest [ASVspoof 5 evaluation](https://arxiv.org/abs/2601.03944) reports degradation under adversarial attacks and neural codecs, reinforcing why a single clean benchmark is insufficient.

## Readiness boundary

Ready to demonstrate the repaired local evidence pipeline and disclose these findings. Not signed off for worldwide fraud detection, calibrated percentages, automatic blocking, or identity authentication. PostgreSQL-backed persistence integration, a physical CallVault call, real same/different-speaker trials, fresh blind telephone data, access control and public deployment security remain unvalidated. Older `backend/app` routes include placeholder context and filename-based demo scores; use `ml.server` for this demo.

SIH's official college guidance has emphasized novelty, practicality, impact and user experience. Present the working prototype, failure cases and measurable upgrade plan; do not substitute an unsupported accuracy claim for validation. The cited document is the **2024** guidance, not confirmation of 2026 eligibility or dates. [Official SIH college guidance](https://sih.gov.in/letters/Guidelines-College-SPOC.pdf).
