"""Reproducible local model audit; never uploads recordings or trains detectors.

historical: recompute metrics from existing scores (not a fresh inference claim).
live: run the deployed adapters on deterministic 3-second windows and controls.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def read_rows(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def metrics(y, scores, threshold=0.5):
    from sklearn.metrics import roc_auc_score, roc_curve, brier_score_loss
    y, scores = np.asarray(y), np.asarray(scores, dtype=float)
    pred = scores >= threshold
    out = {"n": len(y), "genuine": int(sum(y == 0)), "spoof": int(sum(y == 1)),
           "threshold": float(threshold), "mean_score": float(scores.mean()),
           "false_positive_rate": float(pred[y == 0].mean()) if any(y == 0) else None,
           "miss_rate": float((~pred[y == 1]).mean()) if any(y == 1) else None}
    if len(set(y)) == 2:
        fpr, tpr, _ = roc_curve(y, scores, drop_intermediate=False)
        delta = fpr - (1 - tpr)
        hi = int(np.flatnonzero(delta >= 0)[0])
        lo = max(0, hi - 1)
        ratio = 0 if hi == lo else -delta[lo] / (delta[hi] - delta[lo])
        out.update(auc=float(roc_auc_score(y, scores)),
                   eer=float(fpr[lo] + ratio * (fpr[hi] - fpr[lo])))
    if np.all((scores >= 0) & (scores <= 1)):
        out["brier"] = float(brier_score_loss(y, scores))
    return out


def historical(args):
    # Use (set, path), and reject inconsistent metadata instead of silent joins.
    joined = {}
    files = [(ROOT / "research/pipeline_scores.jsonl", {"indic": "indic_v01", "dhwani": "dhwani", "customDeepfake": "custom"}),
             (ROOT / "research/prosody_scores.jsonl", {"prosody": "prosody"})]
    if args.corpus_root:
        base = args.corpus_root / "results"
        files += [(base / "iv15_scores.jsonl", {"p_spoof": "indic_iv15"}),
                  (base / "stage_a_scores.jsonl", {"logit_bonafide": "stageA"}),
                  (base / "spectra_scores_preemph.jsonl", {"logit_bonafide": "spectra"})]
    hashes = {}
    for path, mapping in files:
        if not path.exists():
            continue
        hashes[str(path)] = digest(path)
        for row in read_rows(path):
            key = (row.get("set", "internal"), row["path"])
            current = joined.setdefault(key, {k: row.get(k) for k in ("path", "set", "label", "split", "language", "source", "generator")})
            for name in ("label", "split", "language"):
                if current[name] is not None and row.get(name) is not None and current[name] != row[name]:
                    raise ValueError(f"Conflicting {name}: {key}")
            for src, dst in mapping.items():
                if row.get(src) is not None:
                    current[dst] = -float(row[src]) if dst in {"stageA", "spectra"} else float(row[src])
    rows = list(joined.values())
    models = ["indic_v01", "indic_iv15", "dhwani", "custom", "prosody", "stageA", "spectra"]
    report = {"kind": "historical score reanalysis", "files_sha256": hashes,
              "limitations": ["Scores use whole-clip adapter contracts, not common live 3-second windows.",
                              "Older indic scores are v0.1, not the deployed iv15.",
                              "Speaker independence and model-training overlap are not established by these score files.",
                              "EER sweeps test thresholds for description; fixed-threshold metrics use dev only.",
                              "No deployment weights are selected from test or external performance."],
              "rows": len(rows), "models": {}}
    if args.corpus_root:
        manifest = args.corpus_root / "data/mixed_f5_iv15/manifest.jsonl"
        if manifest.exists():
            manifest_rows = read_rows(manifest)
            split_hashes = defaultdict(set)
            for r in manifest_rows:
                if r.get("sha256"):
                    split_hashes[str(r.get("split"))].add(r["sha256"])
            report["manifest_audit"] = {
                "sha256": digest(manifest), "rows": len(manifest_rows),
                "unknown_speaker_rows": sum(r.get("speaker_id") in {None, "unknown", ""} for r in manifest_rows),
                "split_counts": dict(Counter(str(r.get("split")) for r in manifest_rows)),
                "identical_hash_overlap": {f"{a}:{b}": len(split_hashes[a] & split_hashes[b])
                                           for a in sorted(split_hashes) for b in sorted(split_hashes) if a < b}}
    for row in rows:
        if all(k in row for k in ["indic_v01", "dhwani", "custom", "prosody"]):
            row["legacy_fusion"] = sum(row[k] * w for k, w in zip(["indic_v01", "dhwani", "custom", "prosody"], [.45, .2, .2, .15]))
        if all(k in row for k in ["indic_iv15", "dhwani", "custom", "prosody"]):
            row["current_original_fusion"] = sum(row[k] * w for k, w in zip(["indic_iv15", "dhwani", "custom", "prosody"], [.45, .2, .2, .15]))
            row["detector_only_baseline"] = np.mean([row[k] for k in ["indic_iv15", "dhwani", "custom"]])
    for model in models + ["legacy_fusion", "current_original_fusion", "detector_only_baseline"]:
        usable = [r for r in rows if model in r and np.isfinite(r[model])]
        dev = [r for r in usable if r["split"] == "dev" and r["set"] == "internal"]
        if not dev:
            continue
        # Threshold chosen to meet <=5% empirical genuine false alarms on dev.
        genuine = sorted(r[model] for r in dev if r["label"] == 0)
        threshold = float(np.nextafter(genuine[min(len(genuine)-1, int(np.ceil(.95*len(genuine)))-1)], np.inf))
        subsets = {"dev": dev,
                   "test": [r for r in usable if r["split"] == "test" and r["set"] == "internal"],
                   "external": [r for r in usable if r["set"] == "external"]}
        out = {"coverage": len(usable), "dev_threshold_at_5pct_fpr": threshold, "subsets": {}}
        for name, subset in subsets.items():
            if subset:
                out["subsets"][name] = metrics([r["label"] for r in subset], [r[model] for r in subset], threshold)
        for field in ["language", "generator", "source"]:
            out[field] = {}
            for value in sorted({str(r.get(field)) for r in usable if r["split"] != "dev"}):
                group = [r for r in usable if str(r.get(field)) == value and (r["split"] == "test" or r["set"] == "external")]
                if group:
                    out[field][value] = metrics([r["label"] for r in group], [r[model] for r in group], threshold)
        report["models"][model] = out
    return report


def live(args):
    import soundfile as sf
    import soxr
    import torch
    torch.set_num_threads(2)
    from ml.server.main import _load_all_models
    from ml.pipeline.inference import run_inference
    from ml.pipeline.results import build_score_response
    from ml.adapters import dhwani, deepfake, indic, speaker, prosody
    _load_all_models()
    records = []
    buckets = defaultdict(list)
    manifests = [(args.corpus_root / "data/mixed_f5_iv15/manifest.jsonl", args.corpus_root, "internal"),
                 (args.corpus_root / "data/external2/manifest.jsonl", args.corpus_root / "data/external2", "external")]
    provenance = {}
    for manifest, base, domain in manifests:
        provenance[str(manifest)] = digest(manifest)
        for row in read_rows(manifest):
            if row.get("split") not in {"dev", "test", None} and domain == "internal":
                continue
            if (base / row["path"]).exists():
                key = (domain, str(row.get("split")), str(row.get("language")), row["label"])
                buckets[key].append((row, base, domain))
    chosen = []
    for key in sorted(buckets):
        chosen.extend(sorted(buckets[key], key=lambda x: hashlib.sha256(x[0]["path"].encode()).hexdigest())[:args.per_group])
    def score(y, metadata):
        raw = run_inference(y, "model-audit", len(records))
        response = build_score_response("model-audit", len(records), 0, raw)
        records.append({**metadata, "output": response})
        print(f"{len(records)} {metadata.get('case', metadata.get('language'))} risk={response.get('risk')} errors={raw['model_errors']}", flush=True)
    reference = None
    for row, base, domain in chosen:
        y, sr = sf.read(base / row["path"], dtype="float32", always_2d=True)
        y = y.mean(axis=1)
        if sr != 16000:
            y = soxr.resample(y, sr, 16000).astype(np.float32)
        # Match the live contract: first chunk, no speech-based cherry-picking.
        y = y[:48000]
        if reference is None and row["label"] == 0 and len(y) == 48000:
            reference = y.copy()
        score(y, {k: row.get(k) for k in ["path", "label", "language", "split", "generator", "source"]} | {"set": domain})
    rng = np.random.default_rng(20260907)
    controls = {"silence": np.zeros(48000, np.float32), "too_short": np.ones(160, np.float32)*.1,
                "nan": np.full(48000, np.nan, np.float32), "white_noise": rng.normal(0, .03, 48000).astype(np.float32),
                "dc": np.ones(48000, np.float32)*.1}
    if reference is not None:
        controls.update({"quiet_speech": reference*.01, "clipped_speech": np.clip(reference*30, -1, 1),
                         "telephone_8k": soxr.resample(soxr.resample(reference, 16000, 8000), 8000, 16000).astype(np.float32),
                         "speech_plus_noise": reference + rng.normal(0, .02, len(reference)).astype(np.float32)})
    for name, y in controls.items():
        score(y, {"case": name, "label": None})
    speaker_diagnostics = {"loaded": speaker.is_loaded(), "identity_accuracy_validated": False}
    if speaker.is_loaded() and reference is not None:
        first = speaker._embedder.embed(reference)
        second = speaker._embedder.embed(reference)
        speaker_diagnostics.update(dimension=int(first.size), finite=bool(np.isfinite(first).all()),
                                   self_cosine=speaker._cosine_similarity(first, second),
                                   max_repeat_difference=float(np.max(np.abs(first-second))),
                                   enrollment_count=len(speaker._enrolled_speakers or {}))
    model_summary = {}
    for name, key in [("dhwani", "synthetic_probability"), ("indic", "synthetic_probability"), ("custom_deepfake", "deepfake_probability"), ("prosody_analysis", "overall_prosody_risk")]:
        usable = [r for r in records if r["label"] is not None and r["output"]["signals"].get(name) is not None]
        model_summary[name] = metrics([r["label"] for r in usable], [r["output"]["signals"][name][key] for r in usable]) if usable else {"n": 0}
    times = [r["output"]["inference_ms"] for r in records if r["label"] is not None]
    return {"kind": "fresh live adapter smoke audit", "manifest_sha256": provenance,
            "contract": "first <=3 seconds, mono 16kHz, no selection by score", "seed": 20260907,
            "limitations": ["Small stratified smoke sample; not independent deployment validation.", "Default 0.5 metrics are descriptive, not tuned operating thresholds.", "Noise controls have no speech label."],
            "versions": {m.__name__: m.get_version() for m in [dhwani, deepfake, indic, speaker, prosody]},
            "latency_ms": {"p50": float(np.median(times)), "p95": float(np.percentile(times, 95))},
            "speaker_diagnostics": speaker_diagnostics, "model_summary": model_summary, "records": records}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["historical", "live"])
    ap.add_argument("--corpus-root", type=Path)
    ap.add_argument("--per-group", type=int, default=2)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.mode == "live" and (not args.corpus_root or args.per_group < 1):
        ap.error("live requires --corpus-root and positive --per-group")
    report = historical(args) if args.mode == "historical" else live(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"Report: {args.out}")


if __name__ == "__main__":
    main()
