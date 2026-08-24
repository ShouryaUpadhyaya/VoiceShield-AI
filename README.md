# VoiceShield AI

Real-time voice deepfake detection for live calls. Multi-signal risk fusion with
active prevention.

## Status

| Component | State |
|---|---|
| Audio preprocessing front-end | **Built & tested** — shared by training and serving, 34 unit tests |
| ASVspoof 2019 LA data pipeline | **Built** — integrity-verified cache + manifests |
| Telephony codec augmentation | **Built** — offline render, 7 codecs |
| Deepfake detection model | **Training** — WavLM + LFCC/MGD fusion, variable-length 2-4 s |
| MGD phase features | **Built & tested** — 75 % more phase-sensitive than LFCC |
| Metric validation | **Verified** — reproduces all 4 official ASVspoof 2021 baselines exactly |
| FastAPI backend | **Wired to the real model** (was a `random.uniform()` mock) |
| Speaker verification | Placeholder — labelled as such in the API response |
| Prosody analysis | Placeholder — labelled as such in the API response |
| Risk fusion + prevention | Real rule-based logic |
| React frontend | Working file-upload UI |

The API response includes a `signal_provenance` block stating which signals come
from a model and which are still placeholders. Nothing is presented as measured
when it is not.

## Quickstart

```bash
# 1. Environment (Python 3.11; torch comes from the CUDA index separately)
uv venv --python 3.11 .venv
uv pip install --python .venv --index-url https://download.pytorch.org/whl/cu126 \
    -r ml/requirements-torch.txt
uv pip install --python .venv -r ml/requirements.txt

# 2. Data (~7.5 GB; resumable, safe to interrupt)
./ml/data/download_asvspoof.sh

# 3. Cache + manifests (fails loudly if the corpus does not match the official release)
PYTHONPATH=. .venv/bin/python ml/data/build_cache.py --splits train dev eval

# 4. Offline telephony-codec variants for the training split
PYTHONPATH=. .venv/bin/python -c \
    "from ml.data.build_cache import build_codec_variant; build_codec_variant('train')"

# 5. Train
PYTHONPATH=. .venv/bin/python ml/deepfake_detection/training/train.py

# 6. Evaluate on unseen attacks
PYTHONPATH=. .venv/bin/python ml/deepfake_detection/training/validate.py \
    --checkpoint ml/artifacts/<run>/best.pt --split eval --codec-robustness

# 7. Serve
PYTHONPATH=. .venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000
cd frontend && npm install && npm run dev
```

`GET /health` reports whether the detector is actually loaded, so a degraded
deployment is visible instead of silently scoring every call as genuine.

## Layout

```
ml/common/audio_utils.py        the shared front-end — imported by training AND serving
ml/common/constants.py          the audio contract (sample rate, segment length, policies)
ml/data/build_cache.py          parquet -> int16 memmap + manifests, with integrity gates
ml/data/silence_leak_check.py   measures the ASVspoof silence shortcut
ml/deepfake_detection/
    preprocessing/augment.py    RawBoost + telephony codec simulation
    preprocessing/dataset.py    Dataset over the cache, clean/codec variant sampling
    models/ssl_model.py         frozen WavLM + learned layer weights + attentive pooling
    models/baseline_model.py    LFCC + CNN comparison baseline
    training/train.py           training loop, calibration, checkpointing
    training/validate.py        EER / per-attack / codec robustness reporting
    evaluation/metrics.py       EER, min t-DCF, operating-point metrics
    inference/predictor.py      serving predictor — window pooling + calibration
backend/                        FastAPI service
frontend/                       React + Vite UI
docs/research/preprocessing.md  pipeline decisions and the measurements behind them
```

## Design notes

**One front-end, two callers.** `ml/common/audio_utils.py` is imported by both
the training pipeline and the API predictor. Train/serve preprocessing drift is
the most common reason a model with a good offline score fails on stage.

**The silence shortcut is real and was measured.** On ASVspoof 2019 LA, edge
silence alone separates bonafide from spoof at 34.8 % EER. Edge trimming is
therefore the default. See `docs/research/preprocessing.md`.

**Trained for phone calls, not studio audio.** Training data is rendered through
G.711, GSM, AMR-NB, Opus and MP3. Vocoder artefacts live above 4 kHz, which is
exactly what a narrowband call throws away.

**Sized for the hardware.** On a 4 GB GTX 1650 the SSL encoder is frozen (627 k
trainable of 95 M) and mixed precision is deliberately **off** — fp16 measured
4× *slower* on a card with no tensor cores.

## Data and protocol

**Train** on ASVspoof 2019 LA. **Evaluate** on ASVspoof 2021 DF/LA eval.

2021 is an evaluation-only release with no training partition; this is the
official protocol every published 2021 number uses. See
`docs/research/evaluation_protocol.md`, including the metric validation that
reproduces all four official 2021 DF baselines exactly (RawNet2 22.38 % is the
target to beat).

ASVspoof 2019 LA and 2021, Open Data Commons Attribution License (ODC-By 1.0).
Cite Todisco et al., *ASVspoof 2019: Future Horizons in Spoofed and Fake Audio
Detection*, Interspeech 2019, and Yamagishi et al., *ASVspoof 2021*, 2021.
