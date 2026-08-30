"""Load the official ASVspoof 2021 RawNet2 checkpoint into VoiceShield's RawNet.

WHY THIS WORKS AT ALL
---------------------
VoiceShield's `model.py` is the official ASVspoof 2021 Baseline-RawNet2 with a second
classification head bolted on. Diffed against
`asvspoof-challenge/2021/LA/Baseline-RawNet2/model.py`, the only differences are:

  1. the author comment,
  2. `SincConv(sample_rate=16000)` -> `24000`,
  3. `fc1_gru`/`fc2_gru` renamed to `fc1_binary_gru`/`fc2_binary_gru`, plus an extra
     `fc1_multi_gru`/`fc2_multi_gru` 7-class LibriSeVoc head,
  4. `forward` returns `(binary, multi)` instead of a single tensor.

SincConv, Residual_block, all six blocks, the attention FCs and the GRU are byte
identical. So the official weights transfer with a two-key rename and nothing else:

    119/123 tensors, 0 unexpected keys, 17,623,671/18,680,446 params = 94.3%

The only tensors left uninitialised are the LibriSeVoc multi-class head, which the
Indic path does not train.

`tests/test_equivalence.py` proves the adaptation is numerically exact: the official
model and this one produce bit-identical logits (`torch.equal`) on the same input.

TWO TRAPS THIS MODULE GUARDS
----------------------------
1. SAMPLE RATE. `SincConv` has zero learnable parameters -- `band_pass` is recomputed
   from `sample_rate` on every forward and is NOT in the checkpoint. The official
   weights were trained against a 16 kHz filter bank. Building the model at this
   fork's 24000 default and loading these weights raises no error and crashes
   nothing; it just feeds trained weights a filter bank they have never seen. We
   assert the rate instead of trusting the caller.

2. CONFIG MUTATION. `RawNet.__init__` mutates the dict it is handed
   (`d_args['filts'][2][0] = d_args['filts'][2][1]`), so building a second RawNet
   from the same dict dies with "running_mean should contain 20 elements not 128".
   This is upstream-official behaviour, not a fork defect, so we work around it here
   with a deep copy rather than patching `model.py`.
"""

from __future__ import annotations

import copy
import hashlib
import sys
from pathlib import Path

import torch
import yaml

# fork name <- official name
HEAD_RENAME = {"fc1_gru": "fc1_binary_gru", "fc2_gru": "fc2_binary_gru"}

# The LibriSeVoc head has no counterpart in the official checkpoint. Expected to be
# missing; anything else missing means the adaptation broke.
EXPECTED_MISSING = {
    "fc1_multi_gru.weight", "fc1_multi_gru.bias",
    "fc2_multi_gru.weight", "fc2_multi_gru.bias",
}

# THE OFFICIAL CHECKPOINT'S CLASS ORDER IS THE OPPOSITE OF OURS.
# `asvspoof-challenge/2021` `LA/Baseline-RawNet2/data_utils.py` builds its labels as
#
#     d_meta[key] = 1 if label == 'bonafide' else 0
#
# so in the pretrained head index 1 is BONAFIDE and index 0 is SPOOF. Our manifests use
# the opposite (1 = spoof), which is the natural orientation for reporting P(spoof).
#
# Two consequences, both handled explicitly rather than left to chance:
#   * scoring the FROZEN checkpoint, P(spoof) must be read from index 0;
#   * fine-tuning it under our labels would otherwise force the pretrained head to
#     invert its own meaning, throwing away what it already knows. `swap_binary_head`
#     permutes the two output rows once at load time so the head starts out already
#     agreeing with our convention.
PRETRAINED_SPOOF_INDEX = 0
OUR_SPOOF_INDEX = 1

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CKPT = REPO_ROOT / "weights" / "pre_trained_DF_RawNet2.pth"
DEFAULT_CONFIG = REPO_ROOT / "model_config_RawNet.yaml"

# From weights/PROVENANCE.md. Guards against a truncated or substituted download --
# the asvspoof.org transfer is slow and a partial file is easy to end up with.
EXPECTED_SHA256 = "52d8ad5f524a0f600c7c876d7a157a8f06c44a03504d0b2795c852f5e42c9127"
EXPECTED_SIZE = 70_515_422


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def load_config(path: Path | str = DEFAULT_CONFIG) -> dict:
    """Model config, deep-copied so the caller's dict survives RawNet.__init__."""
    with open(path, "r") as fh:
        return copy.deepcopy(yaml.safe_load(fh)["model"])


def build_model(config: dict | None = None, device: str = "cpu"):
    """Construct RawNet without letting __init__ mutate the caller's config."""
    # Works whether this is imported as a package or run as a script from weights/.
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from model import RawNet

    cfg = load_config() if config is None else copy.deepcopy(config)
    return RawNet(cfg, device)


def load_pretrained(
    model=None,
    ckpt_path: Path | str = DEFAULT_CKPT,
    device: str = "cpu",
    verify_hash: bool = True,
    strict_expectations: bool = True,
):
    """Initialise `model` from the official checkpoint. Returns (model, report)."""
    ckpt_path = Path(ckpt_path)
    if not ckpt_path.exists():
        raise FileNotFoundError(
            f"{ckpt_path} not found. Download and unzip:\n"
            "  https://www.asvspoof.org/asvspoof2021/pre_trained_DF_RawNet2.zip\n"
            "See weights/PROVENANCE.md."
        )

    if verify_hash:
        size = ckpt_path.stat().st_size
        if size != EXPECTED_SIZE:
            raise ValueError(
                f"{ckpt_path.name} is {size} bytes, expected {EXPECTED_SIZE}. "
                "The download is most likely truncated -- re-fetch with `curl -C -`."
            )
        digest = sha256_of(ckpt_path)
        if digest != EXPECTED_SHA256:
            raise ValueError(
                f"{ckpt_path.name} sha256 {digest} != expected {EXPECTED_SHA256}."
            )

    if model is None:
        model = build_model(device=device)

    # SincConv keeps its own `device` attribute and moves the filter bank there inside
    # forward(), so `.to(cuda)` on the module is not enough -- it must be constructed on
    # the target device. Catch that here rather than at the first conv.
    sinc_device = str(getattr(model.Sinc_conv, "device", "cpu"))
    if not str(device).startswith(sinc_device.split(":")[0]):
        raise ValueError(
            f"model was built on '{sinc_device}' but is being loaded for '{device}'. "
            f"Construct it with build_model(cfg, device='{device}') -- SincConv's filter "
            "bank follows its construction device, not .to()."
        )

    # Trap 1: the filter bank is derived from this, not restored from the checkpoint.
    rate = getattr(model.Sinc_conv, "sample_rate", None)
    if rate != 16_000:
        raise ValueError(
            f"SincConv.sample_rate is {rate}, but the official weights were trained "
            "at 16000. Set `sample_rate: 16000` in model_config_RawNet.yaml -- "
            "loading them at another rate fails silently, not loudly."
        )

    # weights_only=True: torch flipped this default in 2.6, but stating it explicitly
    # keeps the guarantee if the pin is ever moved backwards.
    state = torch.load(ckpt_path, map_location=device, weights_only=True)
    state = state.get("state_dict", state)
    state = {k.replace("module.", "", 1): v for k, v in state.items()}

    renamed = {}
    for key, value in state.items():
        prefix = key.split(".")[0]
        if prefix in HEAD_RENAME:
            key = key.replace(prefix, HEAD_RENAME[prefix], 1)
        renamed[key] = value

    result = model.load_state_dict(renamed, strict=False)
    total = len(model.state_dict())
    missing = set(result.missing_keys)
    covered = sum(v.numel() for k, v in model.state_dict().items() if k not in missing)
    all_params = sum(v.numel() for v in model.state_dict().values())

    report = {
        "matched_tensors": total - len(missing),
        "total_tensors": total,
        "missing_keys": sorted(missing),
        "unexpected_keys": sorted(result.unexpected_keys),
        "params_covered": covered,
        "params_total": all_params,
        "coverage_pct": 100.0 * covered / all_params,
        "sha256": EXPECTED_SHA256 if verify_hash else None,
    }

    if strict_expectations:
        if result.unexpected_keys:
            raise RuntimeError(
                f"Unexpected keys in checkpoint: {sorted(result.unexpected_keys)}. "
                "The rename map is out of date with model.py."
            )
        if missing != EXPECTED_MISSING:
            raise RuntimeError(
                "Missing keys differ from the expected LibriSeVoc head.\n"
                f"  expected: {sorted(EXPECTED_MISSING)}\n"
                f"  got     : {sorted(missing)}"
            )

    return model, report


def swap_binary_head(model):
    """Swap the binary head's two output rows so index 1 becomes spoof.

    Applied to the pretrained weights before fine-tuning, this preserves everything the
    head learned and only relabels which output means what. Without it the first epochs
    are spent unlearning a correct decision boundary that was merely pointed the other
    way.
    """
    with torch.no_grad():
        for name in ("fc2_binary_gru.weight", "fc2_binary_gru.bias"):
            tensor = dict(model.named_parameters())[name.rsplit(".", 1)[0] + "." + name.split(".")[-1]]
            tensor.copy_(tensor.flip(0))
    return model


def _main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ckpt", default=str(DEFAULT_CKPT))
    ap.add_argument("--no-verify-hash", action="store_true")
    args = ap.parse_args()

    model, rep = load_pretrained(ckpt_path=args.ckpt, verify_hash=not args.no_verify_hash)
    print(f"checkpoint      : {Path(args.ckpt).name}")
    print(f"sha256 verified : {rep['sha256'] or 'skipped'}")
    print(f"sample_rate     : {model.Sinc_conv.sample_rate}")
    print(f"tensors matched : {rep['matched_tensors']}/{rep['total_tensors']}")
    print(f"unexpected keys : {rep['unexpected_keys'] or 'none'}")
    print(f"missing keys    : {rep['missing_keys']} (LibriSeVoc head, expected)")
    print(f"params covered  : {rep['params_covered']:,}/{rep['params_total']:,} "
          f"= {rep['coverage_pct']:.1f}%")

    model.eval()
    with torch.no_grad():
        binary, _ = model(torch.randn(1, 64_600))
    print(f"forward pass    : ok, binary output {tuple(binary.shape)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
