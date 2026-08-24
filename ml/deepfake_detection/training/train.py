"""Train the spoof detector.

    PYTHONPATH=. .venv/bin/python ml/deepfake_detection/training/train.py \
        --config ml/deepfake_detection/training/config.yaml

Everything needed to reproduce a run — the front-end config, the augmentation
policy, the git commit, the metrics per epoch — is written next to the
checkpoint. A checkpoint whose front-end you cannot reconstruct is a checkpoint
you cannot serve.
"""

from __future__ import annotations

import os

# Fragmentation, not total size, is what kills 4 GB training runs. This must be
# set before torch initialises CUDA, so it happens at import time — setting it
# inside main() is too late, the allocator has already read its config.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import argparse
import json
import math
import random
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import yaml
from torch.utils.data import DataLoader, Subset
from tqdm import tqdm

from ml.common.audio_utils import FrontEndConfig
from ml.common.constants import ARTIFACT_DIR
from ml.deepfake_detection.evaluation.metrics import compute_eer, compute_min_tdcf, metrics_at_threshold
from ml.deepfake_detection.models.classifier import build_model
from ml.deepfake_detection.preprocessing.augment import AugmentConfig, Augmenter
from ml.deepfake_detection.preprocessing.dataset import CachedSpoofDataset, VariableLengthCollator


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def stratified_subset(dataset: CachedSpoofDataset, n: int, seed: int) -> Subset:
    """Keep the bonafide/spoof ratio of the full split.

    A uniform random subsample of a 90%-spoof corpus can land with too few
    bonafide clips to estimate a false-alarm rate at all, which makes the EER
    it reports meaningless.
    """
    if n >= len(dataset):
        return Subset(dataset, list(range(len(dataset))))

    rng = np.random.default_rng(seed)
    labels = dataset.labels
    picks: list[int] = []
    for value in np.unique(labels):
        idx = np.flatnonzero(labels == value)
        take = max(1, round(n * len(idx) / len(labels)))
        picks.extend(rng.choice(idx, size=min(take, len(idx)), replace=False).tolist())
    rng.shuffle(picks)
    return Subset(dataset, picks)


@torch.no_grad()
def evaluate(model, loader, device) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    # Release the training allocator's cached blocks first. On a 4 GB card the
    # reserved-but-unallocated pool from the backward pass is enough on its own
    # to OOM the first eval batch, even though eval needs less memory overall.
    if device == "cuda":
        torch.cuda.empty_cache()
    scores, labels = [], []
    for audio, label in tqdm(loader, desc="eval", leave=False, unit="batch"):
        logits = model(audio.to(device, non_blocking=True))
        scores.append(logits.float().cpu().numpy())
        labels.append(label.numpy())
    return np.concatenate(scores), np.concatenate(labels)


def fit_temperature(scores: np.ndarray, labels: np.ndarray) -> float:
    """Temperature scaling so the API's percentage means something.

    Raw logits pushed through a sigmoid are systematically overconfident. The
    frontend prints this number as "Deepfake Prob", and a confidently wrong 97%
    on a real customer is the failure that gets the system switched off.
    """
    logits = torch.tensor(scores, dtype=torch.float32)
    target = torch.tensor(labels, dtype=torch.float32)
    log_t = torch.zeros(1, requires_grad=True)

    optimizer = torch.optim.LBFGS([log_t], lr=0.1, max_iter=100)

    def closure():
        optimizer.zero_grad()
        loss = F.binary_cross_entropy_with_logits(logits / log_t.exp(), target)
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(log_t.exp().item())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="ml/deepfake_detection/training/config.yaml")
    ap.add_argument("--run-name", default=None)
    ap.add_argument("--limit-train", type=int, default=None, help="cap train utterances (smoke test)")
    ap.add_argument("--epochs", type=int, default=None, help="override config epochs")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    set_seed(cfg["seed"])

    # Fragmentation, not total size, is what kills 4 GB training runs.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    device = "cuda" if torch.cuda.is_available() else "cpu"

    run_name = args.run_name or f"{cfg['model']['name']}_{time.strftime('%Y%m%d_%H%M%S')}"
    out_dir = ARTIFACT_DIR / run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    front_end = FrontEndConfig(**cfg["front_end"])
    aug_cfg = AugmentConfig(**{**cfg["augment"], "gain_db_range": tuple(cfg["augment"]["gain_db_range"])})

    train_set = CachedSpoofDataset(
        cfg["data"]["train_split"], front_end,
        augmenter=Augmenter(aug_cfg, seed=cfg["seed"]),
        crop="random", variants=tuple(cfg["data"]["train_variants"]), seed=cfg["seed"],
    )
    dev_set = CachedSpoofDataset(
        cfg["data"]["dev_split"], front_end,
        augmenter=None, crop="center", variants=tuple(cfg["data"]["dev_variants"]),
    )

    pos_weight = train_set.pos_weight()
    train_view = (
        Subset(train_set, list(range(min(args.limit_train, len(train_set)))))
        if args.limit_train else train_set
    )
    dev_view = stratified_subset(dev_set, cfg["data"]["dev_subsample"], cfg["seed"])

    print(f"train {len(train_view)} utts {train_set.class_counts()} | dev(sub) {len(dev_view)} of {len(dev_set)}")
    print(f"pos_weight={pos_weight:.4f} | variants train={len(train_set.variant_paths)}")

    loader_kwargs = dict(
        num_workers=cfg["data"]["num_workers"], pin_memory=(device == "cuda"),
        persistent_workers=cfg["data"]["num_workers"] > 0,
    )
    vl_cfg = cfg.get("variable_length", {})
    collator = VariableLengthCollator(
        min_samples=vl_cfg.get("min_samples", front_end.segment_samples),
        max_samples=vl_cfg.get("max_samples", front_end.segment_samples),
        seed=cfg["seed"],
        enabled=vl_cfg.get("enabled", False),
    )
    train_loader = DataLoader(
        train_view, batch_size=cfg["training"]["batch_size"], shuffle=True,
        drop_last=True, collate_fn=collator, **loader_kwargs,
    )
    dev_loader = DataLoader(
        dev_view, batch_size=cfg["training"]["eval_batch_size"], shuffle=False, **loader_kwargs
    )

    model_kwargs = {k: v for k, v in cfg["model"].items() if k != "name"}
    model = build_model(cfg["model"]["name"], **model_kwargs).to(device)
    print(f"model: {model.trainable_parameters():,} trainable params")

    # Layer weights are 13 scalars competing with 600k head params; on a shared
    # LR they barely move within the epoch budget.
    layer_params = [p for n, p in model.named_parameters() if n == "layer_weights" and p.requires_grad]
    head_params = [p for n, p in model.named_parameters() if n != "layer_weights" and p.requires_grad]
    optimizer = torch.optim.AdamW(
        [
            {"params": head_params, "lr": cfg["training"]["lr"]},
            {"params": layer_params, "lr": cfg["training"].get("layer_weight_lr", cfg["training"]["lr"])},
        ],
        weight_decay=cfg["training"]["weight_decay"],
    )

    epochs = args.epochs or cfg["training"]["epochs"]
    total_steps = max(1, len(train_loader) * epochs)
    warmup = int(total_steps * cfg["training"]["warmup_ratio"])

    def lr_lambda(step: int) -> float:
        if step < warmup:
            return (step + 1) / max(warmup, 1)
        progress = (step - warmup) / max(total_steps - warmup, 1)
        return 0.5 * (1 + math.cos(math.pi * min(progress, 1.0)))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
    pos_weight_t = torch.tensor([pos_weight], device=device)

    history, best_eer, bad_epochs = [], float("inf"), 0
    for epoch in range(1, epochs + 1):
        model.train()
        running, seen, t0 = 0.0, 0, time.time()
        bar = tqdm(train_loader, desc=f"epoch {epoch}/{epochs}", unit="batch")
        for audio, label in bar:
            audio = audio.to(device, non_blocking=True)
            label = label.float().to(device, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)
            loss = F.binary_cross_entropy_with_logits(model(audio), label, pos_weight=pos_weight_t)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                [p for p in model.parameters() if p.requires_grad], cfg["training"]["grad_clip"]
            )
            optimizer.step()
            scheduler.step()

            running += loss.item() * audio.size(0)
            seen += audio.size(0)
            bar.set_postfix(loss=f"{running/seen:.4f}", lr=f"{scheduler.get_last_lr()[0]:.2e}")

        scores, labels = evaluate(model, dev_loader, device)
        eer, threshold = compute_eer(scores, labels)
        record = {
            "epoch": epoch,
            "train_loss": running / max(seen, 1),
            "dev_eer": eer,
            "dev_threshold": threshold,
            "dev_min_tdcf_cm_only": compute_min_tdcf(scores, labels),
            "seconds": round(time.time() - t0, 1),
            "layer_importance": [round(w, 4) for w in model.layer_importance()]
            if hasattr(model, "layer_importance") else [],
        }
        history.append(record)
        print(f"  epoch {epoch}: loss={record['train_loss']:.4f} dev_EER={eer*100:.2f}% ({record['seconds']}s)")

        if eer < best_eer - 1e-5:
            best_eer, bad_epochs = eer, 0
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "model_name": cfg["model"]["name"],
                    "model_kwargs": model_kwargs,
                    "front_end": asdict(front_end),
                    "variable_length": vl_cfg,
                    "dev_eer": eer,
                    "dev_threshold": threshold,
                    "epoch": epoch,
                },
                out_dir / "best.pt",
            )
            print(f"  saved best.pt (EER {eer*100:.2f}%)")
        else:
            bad_epochs += 1
            if bad_epochs >= cfg["training"]["early_stop_patience"]:
                print(f"  early stop: no improvement in {bad_epochs} epochs")
                break

    # Final pass on the FULL dev set with the best checkpoint, then calibrate.
    checkpoint = torch.load(out_dir / "best.pt", map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state"])
    full_loader = DataLoader(dev_set, batch_size=cfg["training"]["eval_batch_size"], shuffle=False, **loader_kwargs)
    scores, labels = evaluate(model, full_loader, device)
    eer, threshold = compute_eer(scores, labels)
    temperature = fit_temperature(scores, labels)

    checkpoint.update({"dev_eer_full": eer, "dev_threshold": threshold, "temperature": temperature})
    torch.save(checkpoint, out_dir / "best.pt")

    summary = {
        "run": run_name,
        "git_commit": git_commit(),
        "config": cfg,
        "device": torch.cuda.get_device_name(0) if device == "cuda" else "cpu",
        "history": history,
        "final": {
            "dev_eer_full": eer,
            "dev_min_tdcf_cm_only": compute_min_tdcf(scores, labels),
            "threshold": threshold,
            "temperature": temperature,
            "operating_point": metrics_at_threshold(scores, labels, threshold),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary["final"], indent=2, default=str))
    print(f"\nartifacts -> {out_dir}")


if __name__ == "__main__":
    main()
