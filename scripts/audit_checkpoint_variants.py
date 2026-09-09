"""Load each local WavLM checkpoint and check genuine/spoof sample outputs.

This checks saved architecture/front-end compatibility, not detection accuracy.
"""
import argparse
import gc
import json
from pathlib import Path
import sys
import numpy as np
import soundfile as sf
import soxr
import torch
from audit_models import ROOT, digest

sys.path.insert(0, str(ROOT))
from ml.deepfake_detection.inference.predictor import DeepfakePredictor
from ml.adapters.deepfake import _float32_to_wav_bytes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    torch.set_num_threads(2)
    rows = json.loads((ROOT / "docs/research/validation/live_audit.json").read_text())["records"]
    selected = [next(r for r in rows if r["label"] == label and r["set"] == "internal" and r["split"] == "dev") for label in [0, 1]]
    inputs = []
    for row in selected:
        y, sr = sf.read(args.corpus_root / row["path"], dtype="float32", always_2d=True)
        y = y.mean(axis=1)
        if sr != 16000:
            y = soxr.resample(y, sr, 16000).astype(np.float32)
        inputs.append(_float32_to_wav_bytes(y[:48000]))
    output = {"kind": "checkpoint compatibility smoke check", "limitations": ["Two examples per checkpoint cannot measure accuracy."], "models": {}}
    for name in ["wavlm_asp_v1", "ssl_4s_baseline", "fusion_mgd_varlen_v1"]:
        checkpoint = ROOT / "ml/artifacts" / name / "best.pt"
        model = DeepfakePredictor(checkpoint, device="cpu")
        outputs = [{"path": row["path"], "label": row["label"], "output": model.predict(data)} for row, data in zip(selected, inputs)]
        output["models"][name] = {"sha256": digest(checkpoint), "outputs": outputs}
        print(name, [r["output"]["deepfake_probability"] for r in outputs], flush=True)
        del model
        gc.collect()
    args.out.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
