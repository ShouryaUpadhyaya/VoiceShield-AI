"""Quantify the ASVspoof 2019 LA silence shortcut.

Claim under test: leading/trailing silence duration differs systematically
between bonafide and spoofed clips, so a detector can reach a low EER by
measuring silence rather than detecting synthesis.

If that holds, "keep" is not a neutral preprocessing choice — it hands the
model a shortcut that will not exist on a live call, where every clip is cut
by the same VAD. We test it instead of taking it on faith, because the answer
decides the default in constants.py.

Method: for each utterance measure total duration and the duration after edge
trimming, then check how well silence alone separates the classes. A silence-
only EER far below 0.5 is the leak.
"""

from __future__ import annotations

import io
import json

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import soundfile as sf
from tqdm import tqdm

from ml.common.audio_utils import remove_dc, trim_edges
from ml.common.constants import LABEL_SPOOF, METADATA_DIR, RAW_DIR, SAMPLE_RATE
from ml.data.build_cache import parquet_ready
from ml.deepfake_detection.evaluation.metrics import compute_eer

SPLIT_FILES = {"train": "train-00000-of-00001.parquet", "dev": "validation-00000-of-00001.parquet"}

def analyse(split: str, limit: int | None = None) -> pd.DataFrame:
    table = pq.read_table(RAW_DIR / "asvspoof2019_la" / SPLIT_FILES[split], memory_map=True)
    n = table.num_rows if limit is None else min(limit, table.num_rows)

    rows = []
    for i in tqdm(range(n), desc=f"silence:{split}", unit="utt"):
        row = table.slice(i, 1).to_pylist()[0]
        audio, sr = sf.read(io.BytesIO(row["audio"]["bytes"]), dtype="float32", always_2d=True)
        audio = remove_dc(audio.mean(axis=1))

        trimmed = trim_edges(audio)
        system_id = (row.get("system_id") or "-").strip() or "-"
        rows.append({
            "system_id": system_id,
            "label": LABEL_SPOOF if system_id != "-" else 0,
            "total_s": audio.size / sr,
            "speech_s": trimmed.size / sr,
            "silence_s": (audio.size - trimmed.size) / sr,
            "silence_frac": 1.0 - trimmed.size / max(audio.size, 1),
        })
    return pd.DataFrame(rows)


def main() -> None:
    report = {}
    for split in ("train", "dev"):
        path = RAW_DIR / "asvspoof2019_la" / SPLIT_FILES[split]
        if not parquet_ready(path):
            print(f"skip {split}: {path.name} not downloaded yet (or still in flight)")
            continue

        df = analyse(split)
        bona = df[df.label == 0]
        spoof = df[df.label == LABEL_SPOOF]

        # Can silence alone tell the classes apart? Try both directions and
        # keep the better one — a "detector" this cheap is exactly what the
        # model would learn if we let it.
        eer_a, _ = compute_eer(df.silence_s.to_numpy(), df.label.to_numpy())
        eer_b, _ = compute_eer(-df.silence_s.to_numpy(), df.label.to_numpy())
        silence_only_eer = min(eer_a, eer_b)

        eer_dur_a, _ = compute_eer(df.total_s.to_numpy(), df.label.to_numpy())
        eer_dur_b, _ = compute_eer(-df.total_s.to_numpy(), df.label.to_numpy())

        report[split] = {
            "n": len(df),
            "bonafide": {
                "total_s_mean": round(float(bona.total_s.mean()), 3),
                "silence_s_mean": round(float(bona.silence_s.mean()), 3),
                "silence_frac_mean": round(float(bona.silence_frac.mean()), 4),
            },
            "spoof": {
                "total_s_mean": round(float(spoof.total_s.mean()), 3),
                "silence_s_mean": round(float(spoof.silence_s.mean()), 3),
                "silence_frac_mean": round(float(spoof.silence_frac.mean()), 4),
            },
            "silence_only_eer": round(float(silence_only_eer), 4),
            "duration_only_eer": round(float(min(eer_dur_a, eer_dur_b)), 4),
            "silence_s_per_attack": {
                k: round(float(v), 3)
                for k, v in df[df.label == LABEL_SPOOF].groupby("system_id").silence_s.mean().items()
            },
        }
        print(json.dumps({split: report[split]}, indent=2))

    verdict = []
    for split, r in report.items():
        if r["silence_only_eer"] < 0.40:
            verdict.append(
                f"{split}: silence alone separates the classes at {r['silence_only_eer']*100:.1f}% EER "
                f"— a real leak. trim_edges is required, not optional."
            )
        else:
            verdict.append(
                f"{split}: silence alone gives {r['silence_only_eer']*100:.1f}% EER (near chance) "
                f"— no usable leak in this corpus."
            )
    report["verdict"] = verdict

    out = METADATA_DIR / "silence_leak_report.json"
    out.write_text(json.dumps(report, indent=2))
    print("\n" + "\n".join(verdict))
    print(f"\nwritten -> {out}")


if __name__ == "__main__":
    main()
