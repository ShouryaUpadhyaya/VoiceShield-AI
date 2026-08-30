"""VoiceShield backend -- the adapted RawNet2 detector this project trained.

A thin wrapper. It does not change how VoiceShield works: the same `audio_utils` front
end, the same checkpoint, the same dev-fitted threshold. The existing experiments stay
frozen and reproducible; this only presents them through the shared interface.
"""

from __future__ import annotations

import copy
import hashlib
import time
from pathlib import Path

import numpy as np
import torch

from .base import SAMPLE_RATE, DetectionResult

REPO_ROOT = Path(__file__).resolve().parents[1]


class VoiceShieldDetector:
    name = "voiceshield"

    def __init__(self, checkpoint: str | Path, device: str | None = None,
                 normalise: bool = True):
        import sys
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from weights.load_pretrained import build_model

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.checkpoint = Path(checkpoint)
        blob = torch.load(self.checkpoint, map_location=self.device, weights_only=True)

        self.cfg = copy.deepcopy(blob["config"])
        self.nb_samp = self.cfg["nb_samp"]
        self.model_sr = self.cfg.get("sample_rate", SAMPLE_RATE)
        # Read the class index and threshold FROM the checkpoint. Assuming either would
        # silently invert or miscalibrate every verdict.
        self.spoof_index = blob.get("spoof_index", 1)
        self.threshold = blob.get("threshold")
        # Audio contract, taken from the checkpoint. iv15 and every ASDG model were
        # trained on trimmed audio; scoring them untrimmed silently costs 11.5 points
        # of SPRING_F5 detection.
        self.trim = bool(blob.get("trim", False))
        self.normalise = normalise
        self.epoch = blob.get("epoch")
        self.dev_eer = blob.get("dev_eer")

        self.model = build_model(self.cfg, device=self.device).to(self.device)
        self.model.load_state_dict(blob["state_dict"])
        self.model.eval()

        self.sha256 = hashlib.sha256(self.checkpoint.read_bytes()).hexdigest()
        self.version = f"{self.checkpoint.stem}@{self.sha256[:12]}"

    def predict(self, audio_16k_mono: np.ndarray) -> DetectionResult:
        import sys
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from audio_utils import pad, peak_normalise, trim_silence

        y = np.asarray(audio_16k_mono, dtype=np.float32)
        seconds = len(y) / SAMPLE_RATE
        if self.normalise:
            y = peak_normalise(y)
        # Same order as audio_utils.prepare(): normalise, then trim, then window.
        # Doing it in the other order would change what the model sees.
        if self.trim:
            y = trim_silence(y, SAMPLE_RATE)

        # VoiceShield's own windowing: non-overlapping nb_samp windows, tail tiled.
        window = self.nb_samp
        chunks = ([pad(y, window)] if len(y) <= window
                  else [pad(y[i:i + window], window)
                        for i in range(0, len(y), window)
                        if len(y[i:i + window]) > window // 10])

        started = time.perf_counter()
        probs = []
        with torch.no_grad():
            for c in chunks:
                x = torch.from_numpy(np.ascontiguousarray(c)).float().unsqueeze(0)
                binary, _multi = self.model(x.to(self.device))
                probs.append(binary.exp().cpu().numpy()[0])
        latency = (time.perf_counter() - started) * 1000.0

        mean = np.mean(probs, axis=0)
        fake = float(mean[self.spoof_index])
        verdict = None if self.threshold is None else (
            "SPOOF" if fake >= self.threshold else "BONAFIDE")

        return DetectionResult(
            fake_probability=round(fake, 6),
            real_probability=round(1.0 - fake, 6),
            model=self.name, model_version=self.version,
            threshold=self.threshold, verdict=verdict,
            windows_scored=len(chunks), audio_seconds=round(seconds, 2),
            latency_ms=round(latency, 1),
            notes=f"epoch={self.epoch} dev_eer={self.dev_eer}",
        )
