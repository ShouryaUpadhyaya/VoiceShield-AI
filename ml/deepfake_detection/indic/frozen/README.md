# Indic detector checkpoints

Weights are **not** tracked in git (no LFS is configured on this repository). Provision
them here, or point `VOICESHIELD_INDIC_CHECKPOINT` at a file elsewhere.

Resolution order used by `ml/adapters/indic.py`, most-preferred first:

1. `$VOICESHIELD_INDIC_CHECKPOINT` (explicit override)
2. `voiceshield-indic-iv15.pth`  ← **use this**
3. `best_model.pth`
4. `voiceshield-indic-v0.1.pth`  ← superseded, logs `INDIC_SUPERSEDED_CHECKPOINT`

## Why iv15 and not v0.1

Measured on 45 real Indic phone-call recordings, all genuine human speech
(16 kHz containers, true energy 1.6–3.2 kHz, 40–82% silence — i.e. real telephony):

| checkpoint | sha256 (12) | flagged as AI | median `p_spoof` |
|---|---|---|---|
| **iv15** | `171a70affd21` | **2.2%** | **0.0000** |
| v0.1 | `e9937affd88c` | **71.1%** | 0.9946 |

v0.1 is confidently wrong on genuine speech. The cause is the checkpoint, not the
front end: trimming on/off moves v0.1 only 71.1% → 75.6%, and scoring the original
`.ogg` files rather than the converted `.wav` gives 68.2%. Split by bandwidth it
false-accuses across the whole range (100% below 2 kHz, 60% at 2–3 kHz, 78% above
3 kHz), where iv15 is 0.0% below 3 kHz.

Through the pipeline adapter end-to-end the same set goes from 71.1% to **4.4%**.

## Threshold

Do **not** hard-code one. `VoiceShieldDetector` reads `threshold`, `spoof_index` and the
`trim` audio contract from the checkpoint blob, so each file carries its own operating
point (iv15 `0.3316`, v0.1 `0.806`). Swapping the file swaps the threshold with it.
