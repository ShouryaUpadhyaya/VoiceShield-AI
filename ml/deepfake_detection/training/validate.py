"""Evaluate a checkpoint and produce the numbers we are willing to publish.

    PYTHONPATH=. .venv/bin/python ml/deepfake_detection/training/validate.py \
        --checkpoint ml/artifacts/<run>/best.pt --split eval

Reports, in order of how much they actually tell you:

  * EER on unseen attacks (eval split, A07-A19) — the honest headline. Train
    and dev share attacks A01-A06, so a dev EER mostly measures memorisation.
  * Per-attack EER — a single average hides a detector that is blind to one
    synthesis method.
  * Codec robustness — the same eval audio through telephony codecs, which is
    the condition the product actually runs in.
  * Operating-point metrics at the deployed threshold, in the units a user
    experiences: genuine callers wrongly flagged, deepfakes let through.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

from ml.common.audio_utils import FrontEndConfig
from ml.deepfake_detection.evaluation.metrics import (
    compute_eer,
    compute_min_tdcf,
    metrics_at_threshold,
    per_attack_eer,
)
from ml.deepfake_detection.models.classifier import build_model
from ml.deepfake_detection.preprocessing.dataset import CachedSpoofDataset


@torch.no_grad()
def score_split(model, dataset, device: str, batch_size: int) -> np.ndarray:
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=6, pin_memory=True)
    scores = []
    for audio, _ in tqdm(loader, desc="scoring", unit="batch"):
        scores.append(model(audio.to(device, non_blocking=True)).float().cpu().numpy())
    return np.concatenate(scores)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--split", default="eval")
    ap.add_argument("--batch-size", type=int, default=48)
    ap.add_argument("--codec-robustness", action="store_true",
                    help="also score the offline codec render of this split (requires <split>.codec.pcm)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)

    # The front-end must come from the checkpoint, never from current defaults.
    front_end = FrontEndConfig(**checkpoint["front_end"])
    model = build_model(checkpoint["model_name"], **checkpoint["model_kwargs"])
    model.load_state_dict(checkpoint["model_state"])
    model.to(device).eval()

    dataset = CachedSpoofDataset(args.split, front_end, augmenter=None, crop="center", variants=("clean",))
    scores = score_split(model, dataset, device, args.batch_size)
    labels = dataset.labels
    system_ids = dataset.system_ids

    eer, eer_threshold = compute_eer(scores, labels)
    deployed_threshold = float(checkpoint.get("dev_threshold", eer_threshold))

    report = {
        "checkpoint": str(Path(args.checkpoint).resolve()),
        "split": args.split,
        "n_utterances": int(len(labels)),
        "n_bonafide": int((labels == 0).sum()),
        "n_spoof": int((labels == 1).sum()),
        "eer": eer,
        "min_tdcf_cm_only": compute_min_tdcf(scores, labels),
        "eer_threshold": eer_threshold,
        "per_attack_eer": per_attack_eer(scores, labels, system_ids),
        "at_deployed_threshold": metrics_at_threshold(scores, labels, deployed_threshold),
        "at_eer_threshold": metrics_at_threshold(scores, labels, eer_threshold),
    }

    if args.codec_robustness:
        codec_set = CachedSpoofDataset(
            args.split, front_end, augmenter=None, crop="center", variants=("codec",)
        )
        codec_scores = score_split(model, codec_set, device, args.batch_size)
        codec_eer, _ = compute_eer(codec_scores, codec_set.labels)
        report["codec_robustness"] = {
            "eer_clean": eer,
            "eer_telephony_codec": codec_eer,
            "degradation_pp": round((codec_eer - eer) * 100, 2),
        }

    out = Path(args.out) if args.out else Path(args.checkpoint).parent / f"eval_{args.split}.json"
    out.write_text(json.dumps(report, indent=2, default=float))

    print(json.dumps({k: v for k, v in report.items() if k != "per_attack_eer"}, indent=2, default=float))
    print("\nper-attack EER:")
    for attack, value in sorted(report["per_attack_eer"].items(), key=lambda kv: -kv[1]):
        print(f"  {attack}: {value*100:6.2f}%")
    print(f"\nwritten -> {out}")


if __name__ == "__main__":
    main()
