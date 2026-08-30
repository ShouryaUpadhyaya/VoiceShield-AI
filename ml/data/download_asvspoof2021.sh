#!/usr/bin/env bash
# Fetch ASVspoof 2021 evaluation data (DF = deepfake/codec, LA = logical access).
#
# 2021 is an EVALUATION-ONLY release. The official protocol is to train on
# ASVspoof 2019 LA and evaluate here, which is what every published 2021 DF
# number does. Nothing in this script is training data.
#
# Label keys live separately from the audio and are tiny; they are fetched
# first so a partial audio download is still evaluable on whatever landed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="$ROOT/data/raw/asvspoof2021"
mkdir -p "$DEST"

fetch() {  # url, filename
  local url="$1" f="$2"
  if [ -f "$DEST/$f" ]; then echo ">> $f (already complete)"; return; fi
  echo ">> $f"
  curl -L -C - --retry 10 --retry-delay 5 --retry-all-errors \
       --progress-bar -o "$DEST/$f.part" "$url"
  mv "$DEST/$f.part" "$DEST/$f"
}

# 1. Keys and metadata (~47 MB total)
fetch "https://www.asvspoof.org/asvspoof2021/DF-keys-full.tar.gz" "DF-keys-full.tar.gz"
fetch "https://www.asvspoof.org/asvspoof2021/LA-keys-full.tar.gz" "LA-keys-full.tar.gz"

# 2. DF eval part00 first — one part is already a large, representative sample,
#    so we get a real 2021 DF number without waiting for all 34.5 GB.
ZDF="https://zenodo.org/records/4835108/files"
fetch "$ZDF/ASVspoof2021_DF_eval_part00.tar.gz?download=1" "ASVspoof2021_DF_eval_part00.tar.gz"

# 3. LA eval (7.8 GB, single archive)
fetch "https://zenodo.org/records/4837263/files/ASVspoof2021_LA_eval.tar.gz?download=1" \
      "ASVspoof2021_LA_eval.tar.gz"

# 4. Remaining DF parts
for p in 01 02 03; do
  fetch "$ZDF/ASVspoof2021_DF_eval_part$p.tar.gz?download=1" "ASVspoof2021_DF_eval_part$p.tar.gz"
done

echo "done -> $DEST"
