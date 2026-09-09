"""Score our Indic benchmark with every detector the PIPELINE actually contains.

Phases 10-12. Each adapter is called through its own public entry point so it
receives the preprocessing contract it was built with -- we are combining evidence,
not forcing a shared front end.

  indic (v0.1)     RawNet2, 16 kHz, its own normalisation   -> synthetic_probability
  dhwani           ONNX, fixed 48,000 samples (3 s)         -> synthetic_probability
  customDeepfake   WavLM+LFCC/MGD, 64,600, trim+norm        -> deepfake_probability
  prosody          DSP heuristic, no model                  -> overall_prosody_risk

Nothing here fits a calibrator or a weight. It only produces per-clip raw scores so
calibration can later be fitted on dev ALONE. Test clips are scored but never used to
choose anything.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# our research corpus lives in the sibling worktree; read-only
WT = Path("/home/aayushdwivedi/Projects/voiceguard-wt/voiceshield")
SR = 16_000


def load_16k(path: Path) -> np.ndarray:
    y, sr = sf.read(path, dtype="float32", always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1)
    if sr != SR and y.size:
        import soxr
        y = soxr.resample(y, sr, SR).astype(np.float32)
    return np.ascontiguousarray(y.astype(np.float32))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=0, help="0 = all clips")
    ap.add_argument("--models", default="prosody,dhwani,indic,customDeepfake")
    ap.add_argument("--out", default="research/pipeline_scores.jsonl")
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(WT / "data/mixed_f5_iv15/manifest.jsonl")]
    ext = WT / "data/external2"
    for r in rows:
        r["_root"] = "internal"
    erows = [json.loads(l) for l in open(ext / "manifest.jsonl")]
    for r in erows:
        r["_root"] = "external"
    rows += erows
    if a.limit:
        rows = rows[:a.limit]
    resolve = lambda r: (ext / r["path"]) if r["_root"] == "external" else (WT / r["path"])
    rows = [r for r in rows if resolve(r).exists()]
    print(f"clips: {len(rows)}", flush=True)

    want = set(a.models.split(","))
    loaded = {}

    if "prosody" in want:
        from ml.adapters import prosody
        loaded["prosody"] = (prosody, prosody.load_prosody())
    if "dhwani" in want:
        from ml.adapters import dhwani
        # ml/common/constants.py points at models/dhwani/dhwani.onnx, which does not
        # exist; backend/app/services/deepfake_service.py points at the real file. Use
        # the real one so we characterise the model, not the path bug.
        loaded["dhwani"] = (dhwani, dhwani.load_dhwani(
            REPO / "data/external_models/dhwani/best_model.onnx"))
    if "indic" in want:
        from ml.adapters import indic
        # the pipeline hardcodes a path that does not exist on main; point it at the
        # v0.1 checkpoint we actually have, unchanged, and record which file it was
        ck = WT / "frozen/voiceshield-indic-v0.1.pth"
        ok = False
        if ck.exists():
            try:
                from ml.deepfake_detection.indic.detectors.voiceshield_backend import VoiceShieldDetector
                indic._detector = VoiceShieldDetector(checkpoint=ck)
                ok = True
            except Exception as e:
                print(f"  indic load failed: {e}")
        loaded["indic"] = (indic, ok)
    if "customDeepfake" in want:
        from ml.adapters import deepfake
        # predictor.ARTIFACT_DIR is REPO/artifacts; the checkpoints live in ml/artifacts
        loaded["customDeepfake"] = (deepfake, deepfake.load_deepfake(
            REPO / "ml/artifacts/fusion_mgd_varlen_v1/best.pt"))

    for k, (_, ok) in loaded.items():
        print(f"  {k:16} {'LOADED' if ok else 'UNAVAILABLE'}", flush=True)

    out = open(REPO / a.out, "w")
    lat = {k: [] for k in loaded}
    t_start = time.perf_counter()
    for i, r in enumerate(rows):
        y = load_16k(resolve(r))
        rec = {"path": r["path"], "set": r["_root"], "label": r["label"],
               "language": r.get("language"), "source": r.get("source"),
               "generator": r.get("generator"), "split": r.get("split")}
        for name, (mod, ok) in loaded.items():
            if not ok:
                rec[name] = None
                continue
            t0 = time.perf_counter()
            try:
                res = mod.run(y)
            except Exception:
                res = None
            lat[name].append(time.perf_counter() - t0)
            if res is None:
                rec[name] = None
            elif name == "prosody":
                rec[name] = res.get("overall_prosody_risk")
            elif name == "customDeepfake":
                rec[name] = res.get("deepfake_probability")
            else:
                rec[name] = res.get("synthetic_probability")
        out.write(json.dumps(rec) + "\n")
        if i % 250 == 0:
            el = time.perf_counter() - t_start
            print(f"  {i}/{len(rows)}  {el/60:.1f} min", flush=True)
    out.close()
    print(f"\nwrote {a.out}")
    for k, v in lat.items():
        if v:
            print(f"  {k:16} median {1000*np.median(v):7.1f} ms/clip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
