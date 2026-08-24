#!/usr/bin/env bash
# Fetch ASVspoof 2019 LA (official partition counts: 25380 train / 24844 dev / 71237 eval).
#
# Source: HuggingFace parquet mirror of the Edinburgh DataShare release. Chosen
# over datashare.ed.ac.uk because that host serves at ~50 KB/s from here (40+ h
# for the 7.6 GB zip) and the mirror is already mono 16 kHz with system_id
# (attack A01-A19) preserved, which we need for the unseen-attack breakdown.
# Integrity is checked by ml/data/build_manifest.py, which asserts the official
# per-split counts and attack inventory before writing any manifest.
set -euo pipefail

REPO="https://huggingface.co/datasets/Bisher/ASVspoof_2019_LA/resolve/main/data"
DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/data/raw/asvspoof2019_la"
mkdir -p "$DEST"

# train+validation first: enough to train and tune. eval (4.4 GB) can land later.
# Download to <name>.part and rename only on success, so a partially fetched
# file is never visible under its final name. Without this, any reader that
# starts while a download is in flight sees a truncated parquet.
for split in train validation test; do
  f="${split}-00000-of-00001.parquet"
  if [ -f "$DEST/$f" ]; then echo ">> $f (already complete)"; continue; fi
  echo ">> $f"
  curl -L -C - --retry 10 --retry-delay 5 --retry-all-errors \
       --progress-bar -o "$DEST/$f.part" "$REPO/$f"
  mv "$DEST/$f.part" "$DEST/$f"
done
echo "done -> $DEST"
