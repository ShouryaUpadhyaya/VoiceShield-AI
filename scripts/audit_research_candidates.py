"""Run existing sibling-checkout Spectra and Stage A on the live audit's clips.

This is an explicit research comparison, not a deployment loader. Neither model
is added to the service. Model code/checkpoints are read from --corpus-root.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time
import numpy as np
import soundfile as sf
import soxr
import torch
from audit_models import digest, metrics


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-root", type=Path, required=True)
    ap.add_argument("--live-report", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    torch.set_num_threads(2)
    base = args.corpus_root / "models/spectra_aasist"
    spec = importlib.util.spec_from_file_location("_audit_spectra", base / "model.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    model = module.SpectraAASIST.from_pretrained(str(base)).cpu().eval()
    records = [r for r in json.loads(args.live_report.read_text())["records"] if r["label"] is not None]
    output = {"kind": "research candidate smoke comparison", "contract": "first <=3s; preemphasis 0.97 before tile-repeat to 64600; no waveform normalization; higher logit_bonafide means genuine",
              "limitations": ["Small sample; not independent validation.", "These candidates are not integrated into the running service.", "No threshold or probability calibration is claimed."],
              "sha256": {str(base / "model.py"): digest(base / "model.py"), str(base / "model.safetensors"): digest(base / "model.safetensors")},
              "models": {}}
    for name in ["spectra", "stageA"]:
        if name == "stageA":
            head = args.corpus_root / "checkpoints_spectra_stage_a/best.pth"
            blob = torch.load(head, map_location="cpu", weights_only=False)
            model.bridge.load_state_dict(blob["bridge"])
            model.aasist.load_state_dict(blob["aasist"])
            output["sha256"][str(head)] = digest(head)
        predictions = []
        for record in records:
            root = args.corpus_root / "data/external2" if record["set"] == "external" else args.corpus_root
            y, sr = sf.read(root / record["path"], dtype="float32", always_2d=True)
            y = y.mean(axis=1)
            if sr != 16000:
                y = soxr.resample(y, sr, 16000).astype(np.float32)
            y = y[:48000]
            from ml.pipeline.quality import assess_audio
            if not assess_audio(y)["eligible"]:
                continue
            y = np.r_[y[:1], y[1:] - .97*y[:-1]].astype(np.float32)
            y = np.tile(y, int(np.ceil(64600 / len(y))))[:64600]
            start = time.perf_counter()
            with torch.inference_mode():
                logits = model(torch.from_numpy(y).unsqueeze(0))
            predictions.append({"path": record["path"], "set": record["set"], "split": record["split"], "label": record["label"],
                                "logit_spoof_evidence": -float(logits[0, 1]), "latency_ms": 1000*(time.perf_counter()-start)})
        summary = metrics([p["label"] for p in predictions], [p["logit_spoof_evidence"] for p in predictions], 0)
        summary.pop("false_positive_rate", None)
        summary.pop("miss_rate", None)
        summary.pop("threshold", None)
        output["models"][name] = {"summary": summary, "latency_p50_ms": float(np.median([p["latency_ms"] for p in predictions])), "records": predictions}
        print(name, summary, flush=True)
    args.out.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main()
