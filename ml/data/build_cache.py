"""Turn the raw ASVspoof parquet into a training cache + manifests.

Why a cache at all: decoding 25k FLACs and running the front-end on every epoch
would make this machine's 12 CPU cores the bottleneck long before the GPU is
busy. We pay that cost once.

Layout produced (per split):
    data/processed/<split>.pcm    ragged int16, all utterances concatenated
    data/processed/<split>.npz    offsets + lengths + labels + system ids
    data/metadata/labels.csv      human-readable manifest for every utterance
    data/metadata/speakers.csv    per-speaker counts
    data/metadata/dataset_info.json  provenance + integrity check results

Stored audio is conditioned (mono / 16 kHz / DC-removed / silence policy
applied) but NOT level-normalised and NOT cropped: normalisation is cheap and
deterministic so it happens at load, and keeping full length lets training take
a different random 4 s crop each epoch.

int16 is not a quality compromise here — the source corpus is 16-bit PCM, so
this is the original resolution, at half the disk of float32.
"""

from __future__ import annotations

import argparse
import io
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import soundfile as sf
from tqdm import tqdm

from ml.common.audio_utils import FrontEndConfig, apply_silence_policy, remove_dc, resample
from ml.common.constants import (
    LABEL_BONAFIDE,
    LABEL_SPOOF,
    METADATA_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    SAMPLE_RATE,
)

# Official ASVspoof 2019 LA partition sizes. If a mirror disagrees with these
# we stop, rather than silently training on a truncated corpus.
EXPECTED_COUNTS = {"train": 25_380, "dev": 24_844, "eval": 71_237}

# Attacks are disjoint by design: train/dev see A01-A06, eval is dominated by
# A07-A19 which the model has never seen. That split is the whole point of the
# benchmark, so we verify it instead of assuming it.
EXPECTED_ATTACKS = {
    "train": {"A01", "A02", "A03", "A04", "A05", "A06"},
    "dev": {"A01", "A02", "A03", "A04", "A05", "A06"},
    "eval": {f"A{i:02d}" for i in range(7, 20)},
}

SPLIT_FILES = {
    "train": "train-00000-of-00001.parquet",
    "dev": "validation-00000-of-00001.parquet",
    "eval": "test-00000-of-00001.parquet",
}


def parquet_ready(path: Path) -> bool:
    """True only if the file exists and is a complete parquet.

    Downloads land over minutes; a reader that starts mid-transfer gets
    'Parquet magic bytes not found in footer'. Checking the footer up front is
    cheaper and clearer than catching that exception deeper in the pipeline.
    """
    path = Path(path)
    if not path.exists() or path.stat().st_size < 8:
        return False
    try:
        pq.ParquetFile(path).metadata
        return True
    except Exception:
        return False


def _decode_row(audio_field: dict) -> tuple[np.ndarray, int]:
    """Parquet stores audio as {'bytes': <encoded>, 'path': <name>}."""
    data = audio_field.get("bytes")
    if data is None:
        raise ValueError("parquet row has no audio bytes")
    wav, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    return wav.mean(axis=1), sr


def build_split(
    split: str,
    parquet_path: Path,
    front_end: FrontEndConfig,
    limit: int | None = None,
) -> pd.DataFrame:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    pcm_path = PROCESSED_DIR / f"{split}.pcm"
    idx_path = PROCESSED_DIR / f"{split}.npz"

    table = pq.read_table(parquet_path, memory_map=True)
    n_rows = table.num_rows if limit is None else min(limit, table.num_rows)

    rows: list[dict] = []
    offsets = np.zeros(n_rows + 1, dtype=np.int64)
    skipped = 0

    with open(pcm_path, "wb") as sink:
        cursor = 0
        for i in tqdm(range(n_rows), desc=f"cache:{split}", unit="utt"):
            row = table.slice(i, 1).to_pylist()[0]
            try:
                audio, sr = _decode_row(row["audio"])
            except Exception:
                skipped += 1
                offsets[i + 1] = cursor
                continue

            if sr != front_end.sample_rate:
                audio = resample(audio, sr, front_end.sample_rate)
            audio = remove_dc(audio)
            audio = apply_silence_policy(audio, front_end.silence_policy, front_end.silence_top_db)

            if audio.size < front_end.sample_rate // 10:  # < 100 ms is not usable speech
                skipped += 1
                offsets[i + 1] = cursor
                continue

            pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
            sink.write(pcm.tobytes())
            cursor += pcm.size
            offsets[i + 1] = cursor

            system_id = (row.get("system_id") or "-").strip() or "-"
            label = LABEL_SPOOF if system_id != "-" else LABEL_BONAFIDE
            # `key` is the mirror's own label column; cross-check it against the
            # system_id we derived. Disagreement means the mirror is untrustworthy.
            key = row.get("key")
            key_label = key if isinstance(key, int) else (LABEL_SPOOF if key == "spoof" else LABEL_BONAFIDE)
            if key_label != label:
                raise ValueError(
                    f"{split} row {i}: label disagreement — system_id={system_id!r} implies "
                    f"{label} but key column says {key_label}"
                )

            rows.append(
                {
                    "split": split,
                    "index": i,
                    "utt_id": row.get("audio_file_name") or f"{split}_{i}",
                    "speaker_id": row.get("speaker_id") or "unknown",
                    "system_id": system_id,
                    "label": label,
                    "num_samples": int(pcm.size),
                    "duration_s": round(pcm.size / front_end.sample_rate, 3),
                }
            )

    df = pd.DataFrame(rows)
    keep = df["index"].to_numpy()
    np.savez(
        idx_path,
        offsets=offsets,
        keep=keep,
        labels=df["label"].to_numpy(dtype=np.int64),
        system_ids=df["system_id"].to_numpy(dtype=object),
        speaker_ids=df["speaker_id"].to_numpy(dtype=object),
        sample_rate=front_end.sample_rate,
    )

    if skipped:
        print(f"  warning: skipped {skipped} unusable rows in {split}")
    return df


def build_codec_variant(split: str, seed: int = 0, block: int = 512) -> Path:
    """Write <split>.codec.pcm: every utterance pushed through one randomly
    chosen telephony codec.

    Done offline because a codec round-trip costs ~650 ms; doing it in the data
    loader would starve the GPU. Offsets are reused unchanged — apply_codec
    length-matches its output — so the variant file is a drop-in second view of
    the same index.

    Work is submitted in blocks rather than one big map: ProcessPoolExecutor.map
    materialises its entire input iterable up front, which for 18 hours of int16
    audio would be several GB of pickled tasks resident at once.
    """
    from concurrent.futures import ProcessPoolExecutor

    from ml.deepfake_detection.preprocessing.augment import available_codecs

    codecs = available_codecs()
    if not codecs:
        raise SystemExit("no ffmpeg codecs available; cannot build codec variant")

    src = PROCESSED_DIR / f"{split}.pcm"
    dst = PROCESSED_DIR / f"{split}.codec.pcm"
    index = np.load(PROCESSED_DIR / f"{split}.npz", allow_pickle=True)
    offsets, keep = index["offsets"], index["keep"]

    audio_mm = np.memmap(src, dtype=np.int16, mode="r")
    rng = np.random.default_rng(seed)
    assignments = rng.choice(codecs, size=len(keep))

    print(f"codec variant for {split}: {len(keep)} utts over {codecs}")
    with open(dst, "wb") as sink, ProcessPoolExecutor() as pool:
        with tqdm(total=len(keep), desc=f"codec:{split}", unit="utt") as bar:
            for begin in range(0, len(keep), block):
                batch = []
                for pos in range(begin, min(begin + block, len(keep))):
                    row = int(keep[pos])
                    start, end = int(offsets[row]), int(offsets[row + 1])
                    batch.append((np.asarray(audio_mm[start:end]), str(assignments[pos])))

                for out in pool.map(_codec_worker, batch, chunksize=8):
                    sink.write(out.tobytes())
                bar.update(len(batch))

    written = dst.stat().st_size // 2
    expected = int(offsets[int(keep[-1]) + 1])
    if written != expected:
        raise SystemExit(f"codec variant length mismatch: {written} != {expected}")
    print(f"  wrote {dst} ({written * 2 / 2**30:.2f} GiB)")
    return dst


def _codec_worker(item: tuple[np.ndarray, str]) -> np.ndarray:
    from ml.deepfake_detection.preprocessing.augment import apply_codec

    pcm, codec = item
    audio = pcm.astype(np.float32) / 32768.0
    out = apply_codec(audio, codec)
    return np.clip(out * 32767.0, -32768, 32767).astype(np.int16)


def verify(split: str, df: pd.DataFrame, strict: bool) -> dict:
    """Integrity gate. A mirror is only as good as what we can check about it."""
    issues = []
    expected = EXPECTED_COUNTS[split]
    if len(df) != expected:
        issues.append(f"count {len(df)} != official {expected}")

    attacks = set(df.loc[df["label"] == LABEL_SPOOF, "system_id"]) - {"-"}
    missing = EXPECTED_ATTACKS[split] - attacks
    unexpected = attacks - EXPECTED_ATTACKS[split]
    if missing:
        issues.append(f"missing attacks {sorted(missing)}")
    if unexpected:
        issues.append(f"unexpected attacks {sorted(unexpected)}")

    if df["speaker_id"].nunique() < 2:
        issues.append("speaker ids look degenerate")

    report = {
        "split": split,
        "n_utterances": int(len(df)),
        "n_bonafide": int((df["label"] == LABEL_BONAFIDE).sum()),
        "n_spoof": int((df["label"] == LABEL_SPOOF).sum()),
        "n_speakers": int(df["speaker_id"].nunique()),
        "attacks": sorted(attacks),
        "hours": round(float(df["duration_s"].sum()) / 3600.0, 2),
        "duration_s": {
            "mean": round(float(df["duration_s"].mean()), 3),
            "p05": round(float(df["duration_s"].quantile(0.05)), 3),
            "p95": round(float(df["duration_s"].quantile(0.95)), 3),
            "max": round(float(df["duration_s"].max()), 3),
        },
        "issues": issues,
    }
    if issues and strict:
        raise SystemExit(f"integrity check failed for {split}: {issues}")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--splits", nargs="+", default=["train", "dev", "eval"])
    ap.add_argument("--silence-policy", default=FrontEndConfig().silence_policy)
    ap.add_argument("--limit", type=int, default=None, help="cap rows per split (smoke tests)")
    ap.add_argument("--no-strict", action="store_true", help="warn instead of failing integrity checks")
    ap.add_argument("--codec-variant", nargs="*", default=[],
                    help="splits to also render through random telephony codecs (usually: train)")
    args = ap.parse_args()

    front_end = FrontEndConfig(silence_policy=args.silence_policy)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    frames, reports = [], []
    for split in args.splits:
        src = RAW_DIR / "asvspoof2019_la" / SPLIT_FILES[split]
        if not parquet_ready(src):
            print(f"skip {split}: {src.name} not downloaded yet (or still in flight)")
            continue
        df = build_split(split, src, front_end, args.limit)
        frames.append(df)
        reports.append(verify(split, df, strict=not args.no_strict and args.limit is None))

    if not frames:
        raise SystemExit("nothing built — run ml/data/download_asvspoof.sh first")

    for split in args.codec_variant:
        if (PROCESSED_DIR / f"{split}.pcm").exists():
            build_codec_variant(split)

    manifest = pd.concat(frames, ignore_index=True)
    manifest.to_csv(METADATA_DIR / "labels.csv", index=False)

    speakers = (
        manifest.groupby(["split", "speaker_id"])
        .agg(n_utterances=("utt_id", "count"),
             n_spoof=("label", "sum"),
             hours=("duration_s", lambda s: round(s.sum() / 3600, 3)))
        .reset_index()
    )
    speakers.to_csv(METADATA_DIR / "speakers.csv", index=False)

    # Speaker overlap across splits would invalidate every number we report.
    overlap = {}
    for a in manifest["split"].unique():
        for b in manifest["split"].unique():
            if a < b:
                shared = set(manifest[manifest.split == a].speaker_id) & set(
                    manifest[manifest.split == b].speaker_id
                )
                if shared:
                    overlap[f"{a}|{b}"] = sorted(shared)

    info = {
        "corpus": "ASVspoof 2019 LA",
        "source": "HuggingFace mirror Bisher/ASVspoof_2019_LA of Edinburgh DataShare DS_10283_3336",
        "license": "Open Data Commons Attribution License (ODC-By 1.0)",
        "front_end": {
            "sample_rate": front_end.sample_rate,
            "silence_policy": front_end.silence_policy,
            "silence_top_db": front_end.silence_top_db,
            "stored": "int16 PCM, DC-removed, NOT level-normalised, NOT cropped",
        },
        "splits": reports,
        "speaker_overlap_between_splits": overlap or "none",
        "attack_overlap_train_eval": sorted(
            set(Counter(manifest[manifest.split == "train"].system_id)) &
            set(Counter(manifest[manifest.split == "eval"].system_id)) - {"-"}
        ),
    }
    (METADATA_DIR / "dataset_info.json").write_text(json.dumps(info, indent=2))

    print(json.dumps(info, indent=2))
    if overlap:
        print("\nWARNING: speakers appear in more than one split — results will be optimistic.")


if __name__ == "__main__":
    main()
