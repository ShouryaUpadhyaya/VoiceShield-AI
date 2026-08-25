"""Dhwani ONNX detector — CPU-only, no torch.

Wraps ayush2635/Dhwani-Multilingual-Deepfake-Audio-Detection-Model
(Wav2Vec2 XLS-R 300M front-end + AASIST back-end, English/Hindi/Tamil/
Telugu/Malayalam).

Two properties of this model are undocumented traps. Both are enforced here
rather than trusted, because each fails SILENTLY — no exception, just wrong
numbers:

1. BATCHING IS BROKEN. Feeding batch=2 or batch=4 returns a single (1, 2)
   result with no error. A naive caller broadcasts one score across every
   window in the batch and is confidently wrong about all but one. We assert
   the batch dimension on every call.

2. INPUT NORMALISATION IS UNDOCUMENTED AND WORTH 12 POINTS OF EER. Wav2Vec2
   expects zero-mean / unit-variance input. Measured on 100 ASVspoof 2019 dev
   clips: raw [-1,1] scores 42% EER, peak-normalised 42%, zero-mean unit-
   variance 30%. Nothing crashes if you get it wrong.

CALIBRATION STATUS: unvalidated. Dhwani was trained on Common Voice Indic +
IndicSynth; ASVspoof 2019 is out-of-domain for it, and ~30% EER there is not
evidence about how it performs in its own domain — it is evidence that we have
no in-domain data to judge it with. Every result carries validated=False so
nothing downstream can quietly treat this as a trustworthy score.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ml.common.audio_utils import FrontEndConfig, preprocess, sliding_windows

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 3 * SAMPLE_RATE      # Dhwani was trained on 3.0 s
FAKE_IDX, REAL_IDX = 0, 1             # measured: index 0 = fake, 1 = real
MAX_WINDOWS = 16                      # cap work for one request


@dataclass
class DetectorResult:
    deepfake_probability: float
    windows_scored: int
    window_probabilities: list[float]
    audio_seconds: float
    model: str
    validated: bool
    available: bool = True


class DhwaniDetector:
    name = "dhwani-xlsr-aasist"
    version = "hf:ayush2635/Dhwani-Multilingual-Deepfake-Audio-Detection-Model"
    window_samples = WINDOW_SAMPLES
    validated = False                 # see CALIBRATION STATUS above

    def __init__(self, model_path: str | Path, threads: int = 4):
        import onnxruntime as ort

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Dhwani model not found at {self.model_path}")

        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        opts.intra_op_num_threads = threads
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            str(self.model_path), opts, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        # The front-end is the SAME code the training pipeline uses; only the
        # window length differs, and it comes from the model, not a constant.
        self.front_end = FrontEndConfig(segment_samples=WINDOW_SAMPLES)
        logger.info("Dhwani loaded from %s (window %.1f s, CPU)",
                    self.model_path.name, WINDOW_SAMPLES / SAMPLE_RATE)

    # -- scoring -----------------------------------------------------------
    @staticmethod
    def _normalise(x: np.ndarray) -> np.ndarray:
        """Zero-mean / unit-variance — the undocumented requirement (trap 2)."""
        return ((x - x.mean()) / (x.std() + 1e-7)).astype(np.float32)

    def _score_one(self, window: np.ndarray) -> float:
        """One window in, one spoof probability out. Batch is always 1."""
        x = self._normalise(window)[None, :]
        out = self.session.run(None, {self.input_name: x})[0]

        # Trap 1: batching silently collapses. Assert rather than trust.
        if out.shape[0] != x.shape[0]:
            raise RuntimeError(
                f"Dhwani returned {out.shape[0]} results for {x.shape[0]} inputs — "
                "batching is unsupported, call with batch=1 only"
            )

        logits = out[0].astype(np.float64)
        # Softmax over [fake, real]; spoof probability is the fake class.
        z = logits - logits.max()
        e = np.exp(z)
        return float(e[FAKE_IDX] / e.sum())

    def predict(self, source) -> DetectorResult:
        audio = preprocess(source, self.front_end, fixed_length=False)
        windows = sliding_windows(audio, WINDOW_SAMPLES)

        if len(windows) > MAX_WINDOWS:
            picks = np.linspace(0, len(windows) - 1, MAX_WINDOWS).astype(int)
            windows = windows[picks]

        probs = [self._score_one(w) for w in windows]

        # High-quantile pooling: a call is compromised if ANY stretch of it is
        # synthetic, but one noisy window should not decide the verdict alone.
        pooled = float(np.quantile(probs, 0.9)) if len(probs) > 1 else float(probs[0])

        return DetectorResult(
            deepfake_probability=round(pooled, 4),
            windows_scored=len(probs),
            window_probabilities=[round(float(p), 4) for p in probs],
            audio_seconds=round(audio.size / SAMPLE_RATE, 2),
            model=self.name,
            validated=self.validated,
        )
