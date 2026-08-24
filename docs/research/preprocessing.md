# Audio preprocessing pipeline

Every decision below is recorded with the measurement that drove it. Where a
choice was made on convention rather than evidence, that is stated too.

## The pipeline

```
upload (wav/mp3/m4a/webm/flac/opus)
  │
  ├─ decode ──────────── libsndfile, ffmpeg fallback for compressed containers
  ├─ mono ─────────────── channel mean
  ├─ resample ─────────── soxr VHQ → 16 kHz
  ├─ DC removal ───────── subtract mean
  ├─ silence policy ───── trim_edges (frame-energy, 40 dB below peak)
  ├─ RMS normalise ────── to −26 dBFS, gain capped to avoid clipping
  └─ fixed length ─────── 64,600 samples (~4.04 s); random crop train / centre eval
                          short clips tiled, never zero-padded
```

Implemented once in `ml/common/audio_utils.py` and imported by **both** the
training pipeline and the FastAPI predictor. Train/serve front-end drift is the
most common cause of a model that scores well offline and fails live, so there
is deliberately no second implementation to drift from.

Augmentation is separate (`preprocessing/augment.py`) and training-only.

## Decisions and the evidence

### Silence handling — measured, not assumed

ASVspoof 2019 LA is known to leak class information through silence duration.
We measured it across all 25,380 training utterances
(`ml/data/silence_leak_check.py`, output in `data/metadata/silence_leak_report.json`):

| | bonafide | spoof |
|---|---|---|
| mean total duration | 3.389 s | 3.430 s |
| mean edge silence | **1.063 s** | **0.810 s** |
| mean silence fraction | 31.3 % | 23.3 % |

Silence duration **alone**, used as the only feature, separates the classes at
**34.8 % EER** — well below the 50 % of a useless feature. Total duration alone
gives 48.9 %, i.e. chance, so the signal is specifically in the silence.

Per attack the mean edge silence ranges from 0.165 s (A01) to 1.530 s (A02), so
a model left to its own devices could partly identify the *synthesis system* by
how much silence it leaves.

**Consequence:** `trim_edges` is the default in `constants.py`. On a live call
every clip is cut by the same VAD, so this cue would not exist in production —
training on it would inflate our reported EER and buy nothing real. The `keep`
policy is retained so both numbers can be reported side by side.

### Level normalisation

Uploads vary in loudness by orders of magnitude. Without normalisation the
model can key on gain. RMS-normalising to −26 dBFS makes two copies of the same
clip at 1 % and 90 % gain land within 0.5 dB of each other (tested). The gain
is capped so normalisation can never clip — clipping is itself an artefact.

Digital silence is left alone rather than amplified to the target level, which
would turn dither into "speech".

### Fixed length: tile, don't zero-pad

64,600 samples is the ASVspoof/AASIST convention, kept so our EER is comparable
to published numbers. Clips shorter than that are **tiled**, not zero-padded: a
block of digital silence is a strong artefact, and if one class is short more
often than the other, padding hands the model a shortcut.

### Telephony codec augmentation

The product runs on phone calls, so training audio has to pass through the
codecs production audio does. Measured effect on spectral centroid of a 180 Hz
test tone with harmonics:

| codec | centroid after | note |
|---|---|---|
| none | 794 Hz | reference |
| G.711 µ-law | 940 Hz | 8 kHz, quantisation noise added |
| Opus 16 kbit/s | 633 Hz | |
| GSM 06.10 | 647 Hz | |
| AMR-NB 12.2 kbit/s | 296 Hz | severe band limiting |

Vocoder artefacts concentrate above 4 kHz, exactly what these codecs discard.
A detector trained only on clean 16 kHz audio has nothing left to look at once
the call is narrowband.

**Cost forced a design choice:** a codec round-trip is ~650 ms/utterance (two
ffmpeg processes). Online, at 50 % probability, that is ~13 minutes of CPU per
epoch against a ~16 minute GPU epoch — the loader would starve the GPU. So
codec variants are rendered **offline** into a parallel `.codec.pcm` file with
byte-identical offsets, and the loader picks between clean and codec views for
free. Online augmentation is RawBoost only, measured at **18.5 ms/utterance**
(~39 s per epoch across 12 workers).

### RawBoost

RawBoost (Tak et al., ICASSP 2022), algorithm 4 = series(1,2,3): linear
convolutive noise, impulsive signal-dependent noise, and coloured additive
noise. Applied to the waveform, needs no external noise corpus. This is the
ASVspoof 2021 standard augmentation.

## Cache format

Decoding 25k FLACs per epoch would make the CPU the bottleneck. The corpus is
conditioned once into a ragged int16 memmap:

```
data/processed/train.pcm        2.10 GiB   concatenated int16
data/processed/train.codec.pcm  2.10 GiB   same utterances, random telephony codec
data/processed/train.npz        offsets, labels, system_ids, speaker_ids
```

int16 is not a quality compromise — the source corpus is 16-bit PCM, so this is
the original resolution at half the disk of float32.

Full-length audio is stored (not pre-cropped) so each epoch can take a
*different* random 4 s crop of the same utterance: free augmentation, no extra
disk.

## Corpus integrity

`ml/data/build_cache.py` refuses to write a manifest unless the data matches
the official ASVspoof 2019 LA release. Verified on the train split:

- 25,380 utterances — official count ✓
- 2,580 bonafide / 22,800 spoof — official split ✓
- 20 speakers — official ✓
- attacks exactly {A01…A06} — official known-attack set ✓
- no speaker overlap between splits ✓
- `system_id` and the label column agree on every row ✓
- 18.26 hours of audio

The corpus was taken from a HuggingFace parquet mirror rather than Edinburgh
DataShare, which served at ~50 KB/s from here (40+ hours for the 7.6 GB zip).
The checks above are what justify trusting the mirror.

## Hardware findings (GTX 1650, 4 GB, 12 cores)

| config | throughput | peak VRAM | epoch (25,380 utts) |
|---|---|---|---|
| batch 8 | 7.7 utt/s | 0.77 GiB | 54.9 min |
| batch 16 | 18.1 utt/s | 1.17 GiB | 23.4 min |
| **batch 32** | **25.4 utt/s** | **1.96 GiB** | **16.6 min** |
| batch 48 | 26.9 utt/s | 2.76 GiB | 15.7 min |
| batch 64 | OOM | — | — |

**Mixed precision is disabled deliberately.** fp16 autocast measured *4× slower*
(5.8 utt/s at batch 32) — the GTX 1650's TU117 die has no tensor cores, so
autocast pays conversion overhead for no compute benefit. This is the opposite
of the usual advice and worth knowing before anyone "optimises" it back on.

Freezing the SSL encoder leaves 627,342 trainable parameters out of 95,009,278
(0.7 %). Full fine-tuning of WavLM-large — the 1.26 % EER recipe from the
literature — needs roughly 24 GB and is not reachable on this machine.
