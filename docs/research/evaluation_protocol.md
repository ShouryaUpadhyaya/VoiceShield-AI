# Evaluation protocol

## The rule

**Train on ASVspoof 2019 LA. Never train on 2021.**

ASVspoof 2021 is an evaluation-only release — Zenodo record 4835108 is
`ASVspoof2021_DF_eval_part00..03` and 4837263 is `ASVspoof2021_LA_eval`. There
is no 2021 training partition, and the official protocol every published 2021
number follows is to train on 2019 LA and evaluate on 2021.

Third-party mirrors exist that carve a "train" split out of the 2021 DF
evaluation set. We deliberately do not use them: training on part of the
evaluation set contaminates the evaluation, breaks comparability with every
published result, and (in the case of the "Balanced_Normalized" mirror) applies
an unverifiable preprocessing step that conflicts with our own front-end.

## Metric validation

Before trusting any number this repo produces, the metric code was checked
against ground truth. The 2021 keys package ships the challenge's own baseline
score files, so `ml/deepfake_detection/evaluation/metrics.py` was used to
recompute all four official DF baselines:

| baseline | ours | published |
|---|---|---|
| LFCC-GMM | 25.25 % | 25.25 % |
| CQCC-GMM | 25.56 % | 25.56 % |
| LFCC-LCNN | 23.48 % | 23.48 % |
| RawNet2 | **22.38 %** | **22.38 %** |

Exact to two decimals on all four. This also pinned down the protocol detail
that makes the difference: published numbers are computed on
`phase == "eval"` (533,928 of the 611,829 trials). Including the `progress` and
`hidden` phases shifts EER by 0.2–0.7 pp.

RawNet2 at 22.38 % is the number to beat.

Reproduce with:

```bash
PYTHONPATH=. .venv/bin/python ml/data/build_asvspoof2021.py --track DF --baselines-only
```

## Evaluation sets, in order of how much they tell you

| set | what it measures | why it matters |
|---|---|---|
| 2019 LA dev | known attacks A01–A06, unseen speakers | sanity/checkpoint selection only — mostly measures memorisation |
| 2019 LA eval | unseen attacks A07–A19, clean audio | first honest generalisation test |
| **2021 DF eval** | unseen attacks under 9 codec conditions | **the headline** — telephony realism, directly comparable to the leaderboard |
| 2021 LA eval | unseen attacks over real telephony channels | codec + transmission effects |

Dev EER is reported but never quoted as the result. Train and dev share attacks
A01–A06, so a low dev EER is expected and largely uninformative — this is the
"catastrophic generalisation failure" trap, where sub-1 % in-domain models
degrade up to twentyfold out of domain.

## The codec breakdown

2021 DF covers each of its 67,981 trials under nine conditions:

```
nocodec  low_mp3  high_mp3  low_m4a  high_m4a  low_ogg  high_ogg  mp3m4a  oggm4a
```

Because the conditions are balanced over the same trials, EER per codec is a
clean measurement rather than a confound. For a product that runs on phone
calls, that table is more informative than the headline average.

The release also labels the synthesis family, which lets us report where the
detector is weakest:

| vocoder family | trials |
|---|---|
| traditional_vocoder | 275,553 |
| neural_vocoder_autoregressive | 152,379 |
| neural_vocoder_nonautoregressive | 120,915 |
| unknown | 29,043 |
| waveform_concatenation | 11,322 |
| bonafide | 22,617 |

## Operating-point targets

The blueprint specifies SLAs, so results are reported against them by name
rather than as an abstract EER:

| metric | target | meaning |
|---|---|---|
| False Acceptance Rate | < 1.5 % | synthetic voices that get through |
| False Rejection Rate | < 3.0 % | genuine callers wrongly flagged |
| Real-Time Factor | ≤ 0.1 | 1 s of audio processed in ≤ 100 ms |
| End-to-end latency | < 500 ms | conversational turn-taking budget |

`metrics_at_threshold()` reports false-alarm and miss rates in exactly these
units. EER is the summary; FAR/FRR at the deployed threshold is what a caller
actually experiences.

## Duration

The model is trained on variable-length crops from 2.0 s to 4.04 s, so it can
be evaluated at both:

* **4.04 s** — comparable to published ASVspoof results.
* **2.0 s** — the streaming window that makes a sub-2 s time-to-alert claim
  honest.

Both numbers get reported. Training at one length and serving at another would
be exactly the train/serve mismatch this codebase is built to avoid.
