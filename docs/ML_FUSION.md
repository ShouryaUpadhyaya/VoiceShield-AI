# ML evidence and fusion policy

The active policy is `sih-evidence-v1`. Its 0–100 result is **synthetic-audio evidence**, not a calibrated probability of fraud. See [the full model audit](research/SIH_MODEL_AUDIT.md) and [demo runbook](SIH_DEMO.md).

## Default configuration

| Model | Weight | Role |
|---|---:|---|
| Indic iv15 | 1.0 | Provisional primary detector |
| Dhwani | 0.0 | Diagnostic comparison |
| Custom WavLM + LFCC/MGD | 0.0 | Diagnostic comparison |
| Prosody | 0.0 | Acoustic supporting evidence |
| ECAPA | Not a fusion input | Enrollment-gallery similarity |

iv15 is the strongest integrated candidate on historical development EER (4.02%, versus 4.46% for the original ensemble and 9.83% for the equal detector average). This selection is provisional for live chunks and does not establish external generalization. All adapters still run so their outputs remain available. Stage A and Spectra are promising research candidates, not integrated models.

The old 0.45/0.20/0.20/0.15 defaults are retired. Prosody is a heuristic, not a comparable synthetic probability; nonzero prosody weights are rejected.

## Calculation and abstention

For explicitly enabled detectors that produce finite values in [0,1], the index is:

`100 × sum(score_i × weight_i) / sum(available positive weights)`

Zero-weight detectors do not become fallback scorers. Under the default profile, missing iv15 means **unknown**, even if Dhwani or prosody loaded. Manual experimental detector weights can be set through `PUT /api/config/fusion`; send all four numeric weights summing to one, with prosody zero. Changes are process-local and are not learned/calibrated weights.

Each response exposes effective weights, contributions, configured weights and detector status. The new `risk` document includes score, reasons, recommended action and `calibrated: false`. The older `signals.deepfake_probability` field is retained for wire compatibility but has the same **uncalibrated evidence-score** semantics.

Silence, DC, nonfinite/malformed input, <1 second or insufficient active audio produce null, never “safe”. The gate is not a VAD. Clipping, missing enabled detectors or a ≥0.5 spread between diagnostic detector scores trigger review. Prosody is excluded from disagreement calculations.

Bands below 40 / 40–75 / ≥75 are provisional display rules; they are not the raw model's decision threshold and do not authorize blocking. No score verifies speaker identity or excludes a human-voiced scam.

## Window and call behavior

Live audio uses three-second chunks. The final partial chunk retains its observed duration; padding is not counted as speech. Uploads up to 60 seconds run the same windows and return all results, their valid-window mean and peak, coverage and review reasons. The gateway stores a valid-window mean, excluding null/nonfinite scores and refreshing it when late results arrive.

`GET /api/calls/:id` also exposes `risk_summary` with mean, peak and unscored-window counts. The dashboard's live mean uses only its last 20 retained chunks and is labeled accordingly.

A mean can conceal a short suspicious segment. Neither mean, max, noisy-OR nor p90 pooling is a calibrated call probability without separate evaluation. Inspect the timeline and peak and validate a call-level operating point before using it for alerts.

## Serving contract

Startup resolves explicit checkpoint overrides strictly and pins default architecture paths. Model versions identify the loaded artifacts. FastAPI lifespan loads models for both `python -m ml.server.main` and `uvicorn ml.server.app:app`. `/ready` requires a scoring detector; a prosody-only process returns 503. Use one process/worker on limited memory.

The older `backend/app` scoring routes have a different policy and placeholder context/demo behavior. They are not part of this validated gateway demo. Use port 8011 and the runbook.
