"""Build an evaluation cache from the ASVspoof 2021 DF / LA release.

ASVspoof 2021 is evaluation-only. The official protocol — and what every
published 2021 number does — is to train on ASVspoof 2019 LA and evaluate here.
Nothing this script produces is training data, and it refuses to be used as
such by writing its manifests under an `eval21_` prefix.

Two properties of the 2021 DF release make it the right telephony benchmark:

* Nine codec conditions (nocodec, low/high mp3, m4a, ogg and combinations),
  each covering the same 67,981 trials, so codec robustness can be measured
  directly instead of inferred.
* Attacks and source corpora unseen in 2019, which is what tests the
  "catastrophic generalisation failure" the model is most at risk of.

The keys package also ships the official baseline score files. Our metrics
reproduce all four published baseline EERs exactly (LFCC-GMM 25.25 %,
CQCC-GMM 25.56 %, LFCC-LCNN 23.48 %, RawNet2 22.38 %) when restricted to
phase == "eval", which is how we know both the metric code and the protocol
filter are right.
"""

from __future__ import annotations

import argparse
import io
import json
import tarfile
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf
from tqdm import tqdm

from ml.common.audio_utils import FrontEndConfig, apply_silence_policy, remove_dc, resample
from ml.common.constants import LABEL_BONAFIDE, LABEL_SPOOF, METADATA_DIR, PROCESSED_DIR, RAW_DIR

RAW_2021 = RAW_DIR / "asvspoof2021"

METADATA_COLUMNS = [
    "speaker_id", "utt_id", "codec", "source", "attack_id", "key",
    "trim", "phase", "vocoder", "task", "team", "gender", "extra",
]

# Published ASVspoof 2021 baseline EERs (%), for the comparison table.
PUBLISHED_BASELINES = {
    "DF": {"LFCC-GMM": 25.25, "CQCC-GMM": 25.56, "LFCC-LCNN": 23.48, "RawNet2": 22.38},
    "LA": {"LFCC-GMM": 19.30, "CQCC-GMM": 15.62, "LFCC-LCNN": 9.26, "RawNet2": 9.50},
}


def load_metadata(track: str = "DF") -> pd.DataFrame:
    path = RAW_2021 / "keys" / track / "CM" / "trial_metadata.txt"
    if not path.exists():
        raise SystemExit(f"missing {path} — run ml/data/download_asvspoof2021.sh first")

    rows = [line.split()[: len(METADATA_COLUMNS)] for line in path.read_text().splitlines() if line.strip()]
    df = pd.DataFrame(rows, columns=METADATA_COLUMNS)
    df["label"] = (df["key"] == "spoof").astype(int)
    return df


def baseline_eers(track: str = "DF", phase: str = "eval") -> dict[str, float]:
    """Recompute the official baselines with OUR metric code.

    Reporting our model next to numbers we computed ourselves, from the
    challenge's own score files, is the only way the comparison is apples to
    apples — and it doubles as a regression test on the metric.
    """
    from ml.deepfake_detection.evaluation.metrics import compute_eer

    meta = load_metadata(track)
    labels = dict(zip(meta.utt_id, meta.label))
    phases = dict(zip(meta.utt_id, meta.phase))

    out: dict[str, float] = {}
    for name in PUBLISHED_BASELINES[track]:
        score_path = RAW_2021 / "keys" / track / "CM" / name / "score.txt"
        if not score_path.exists():
            continue
        utts, scores = [], []
        for line in score_path.read_text().splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            utts.append(parts[0])
            scores.append(float(parts[-1]))

        mask = np.array([phases.get(u) == phase for u in utts])
        # Baseline scores are bonafide-positive; our convention is spoof-positive.
        eer, _ = compute_eer(-np.array(scores)[mask], np.array([labels[u] for u in utts])[mask])
        out[name] = round(eer * 100, 2)
    return out


def build(track: str, phase: str, front_end: FrontEndConfig, limit: int | None = None) -> pd.DataFrame:
    """Decode every available flac from the downloaded tar parts into the cache.

    The release is split across four 8.6 GB archives. Whichever parts are on
    disk get processed, and the manifest records exactly which utterances made
    it, so a partial download still yields a valid (smaller) evaluation.
    """
    meta = load_metadata(track).set_index("utt_id")
    archives = sorted(RAW_2021.glob(f"ASVspoof2021_{track}_eval*.tar.gz"))
    if not archives:
        raise SystemExit(f"no {track} eval archives in {RAW_2021}")

    split = f"eval21_{track.lower()}"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    pcm_path = PROCESSED_DIR / f"{split}.pcm"

    rows: list[dict] = []
    offsets: list[int] = [0]
    cursor = 0
    skipped = 0

    with open(pcm_path, "wb") as sink:
        for archive in archives:
            with tarfile.open(archive, "r|gz") as tar:  # streaming: never extracts to disk
                for member in tqdm(tar, desc=f"{split}:{archive.name}", unit="file"):
                    if not member.name.endswith(".flac"):
                        continue
                    utt_id = Path(member.name).stem
                    if utt_id not in meta.index:
                        skipped += 1
                        continue

                    record = meta.loc[utt_id]
                    if phase != "all" and record["phase"] != phase:
                        continue

                    handle = tar.extractfile(member)
                    if handle is None:
                        skipped += 1
                        continue
                    try:
                        audio, sr = sf.read(io.BytesIO(handle.read()), dtype="float32", always_2d=True)
                    except Exception:
                        skipped += 1
                        continue

                    audio = audio.mean(axis=1)
                    if sr != front_end.sample_rate:
                        audio = resample(audio, sr, front_end.sample_rate)
                    audio = apply_silence_policy(
                        remove_dc(audio), front_end.silence_policy, front_end.silence_top_db
                    )
                    if audio.size < front_end.sample_rate // 10:
                        skipped += 1
                        continue

                    pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
                    sink.write(pcm.tobytes())
                    cursor += pcm.size
                    offsets.append(cursor)

                    rows.append({
                        "split": split,
                        "utt_id": utt_id,
                        "speaker_id": record["speaker_id"],
                        "system_id": record["attack_id"] if record["label"] == LABEL_SPOOF else "-",
                        "codec": record["codec"],
                        "vocoder": record["vocoder"],
                        "phase": record["phase"],
                        "label": int(record["label"]),
                        "num_samples": int(pcm.size),
                        "duration_s": round(pcm.size / front_end.sample_rate, 3),
                    })

                    if limit and len(rows) >= limit:
                        break
            if limit and len(rows) >= limit:
                break

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("no usable audio found — are the archives complete?")

    np.savez(
        PROCESSED_DIR / f"{split}.npz",
        offsets=np.array(offsets, dtype=np.int64),
        keep=np.arange(len(df), dtype=np.int64),
        labels=df["label"].to_numpy(dtype=np.int64),
        system_ids=df["system_id"].to_numpy(dtype=object),
        speaker_ids=df["speaker_id"].to_numpy(dtype=object),
        codecs=df["codec"].to_numpy(dtype=object),
        vocoders=df["vocoder"].to_numpy(dtype=object),
        sample_rate=front_end.sample_rate,
    )
    df.to_csv(METADATA_DIR / f"labels_{split}.csv", index=False)

    info = {
        "corpus": f"ASVspoof 2021 {track} (evaluation only)",
        "protocol": "train on ASVspoof 2019 LA; this set is never trained on",
        "phase_filter": phase,
        "n_utterances": int(len(df)),
        "n_bonafide": int((df.label == LABEL_BONAFIDE).sum()),
        "n_spoof": int((df.label == LABEL_SPOOF).sum()),
        "codecs": {k: int(v) for k, v in df.codec.value_counts().items()},
        "vocoders": {k: int(v) for k, v in df.vocoder.value_counts().items()},
        "hours": round(float(df.duration_s.sum()) / 3600, 2),
        "skipped": skipped,
        "archives_used": [a.name for a in archives],
        "official_baselines_recomputed": baseline_eers(track, phase if phase != "all" else "eval"),
        "official_baselines_published": PUBLISHED_BASELINES[track],
    }
    (METADATA_DIR / f"dataset_info_{split}.json").write_text(json.dumps(info, indent=2))
    print(json.dumps(info, indent=2))
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--track", default="DF", choices=["DF", "LA"])
    ap.add_argument("--phase", default="eval", choices=["eval", "progress", "hidden", "all"],
                    help="official published numbers use 'eval'")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--baselines-only", action="store_true",
                    help="just recompute the official baseline EERs (needs keys only, no audio)")
    args = ap.parse_args()

    if args.baselines_only:
        recomputed = baseline_eers(args.track, args.phase if args.phase != "all" else "eval")
        published = PUBLISHED_BASELINES[args.track]
        print(f"{'baseline':12s} {'ours':>8s} {'published':>10s}")
        for name, value in recomputed.items():
            print(f"{name:12s} {value:7.2f}% {published[name]:9.2f}%")
        return

    build(args.track, args.phase, FrontEndConfig(), args.limit)


if __name__ == "__main__":
    main()
