"""
Dhwani ONNX wrapper.

Dhwani:
    ayush2635/Dhwani-Multilingual-Deepfake-Audio-Detection-Model

Architecture:
    XLS-R 300M -> AASIST

Input:
    16 kHz
    mono
    float32
    exactly 48,000 samples = 3 seconds

IMPORTANT:
The Dhwani model card explicitly requires mean/variance
normalization before inference.
"""

from __future__ import annotations

import numpy as np
import onnxruntime as ort

from ml.common.constants import SAMPLE_RATE, WINDOW_SAMPLES, MODEL_PATHS


class DhwaniDetector:

    def __init__(
        self,
        model_path: str | None = None,
        providers: list[str] | None = None,
    ):
        self.model_path = model_path or MODEL_PATHS["dhwani_onnx"]

        self.providers = providers or [
            "CPUExecutionProvider"
        ]

        self.session = ort.InferenceSession(
            self.model_path,
            providers=self.providers,
        )

        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

        print("Dhwani loaded successfully.")
        print(f"  Model: {self.model_path}")
        print(
            f"  Input: {self.input_name} "
            f"{self.session.get_inputs()[0].shape}"
        )
        print(
            f"  Output: {self.output_name} "
            f"{self.session.get_outputs()[0].shape}"
        )
        print(f"  Providers: {self.session.get_providers()}")

    def _prep(self, audio: np.ndarray) -> np.ndarray:
        """
        Prepare one audio window exactly as required by Dhwani.

        Steps:
        1. Convert to float32
        2. Ensure mono
        3. Truncate/pad to 3 seconds
        4. Mean/variance normalize
        5. Add batch dimension
        """

        audio = np.asarray(audio, dtype=np.float32)

        # ---------------------------------------------------------
        # Ensure mono
        # ---------------------------------------------------------

        if audio.ndim == 2:

            # Handle (samples, channels)
            if audio.shape[1] <= 8:
                audio = np.mean(audio, axis=1)

            # Handle (channels, samples)
            else:
                audio = np.mean(audio, axis=0)

        audio = audio.flatten()

        # ---------------------------------------------------------
        # Remove NaN / Inf
        # ---------------------------------------------------------

        audio = np.nan_to_num(
            audio,
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )

        # ---------------------------------------------------------
        # EXACTLY 3 seconds
        # ---------------------------------------------------------

        if len(audio) > WINDOW_SAMPLES:

            audio = audio[:WINDOW_SAMPLES]

        elif len(audio) < WINDOW_SAMPLES:

            audio = np.pad(
                audio,
                (0, WINDOW_SAMPLES - len(audio)),
                mode="constant",
            )

        # ---------------------------------------------------------
        # Dhwani-required normalization
        #
        # Official model card:
        #
        # y = (y - mean(y)) /
        #     sqrt(var(y) + 1e-5)
        # ---------------------------------------------------------

        mean = np.mean(audio)
        variance = np.var(audio)

        audio = (
            audio - mean
        ) / np.sqrt(
            variance + 1e-5
        )

        audio = audio.astype(np.float32)

        # ---------------------------------------------------------
        # Add batch dimension
        # (48000,) -> (1, 48000)
        # ---------------------------------------------------------

        return audio.reshape(
            1,
            WINDOW_SAMPLES,
        )

    def predict(
        self,
        audio: np.ndarray,
    ) -> float:

        inp = self._prep(audio)

        outputs = self.session.run(
            [self.output_name],
            {
                self.input_name: inp
            },
        )

        logits = np.asarray(
            outputs[0],
            dtype=np.float32,
        ).squeeze()

        # ---------------------------------------------------------
        # Expected Dhwani output:
        #
        # [genuine_logit, synthetic_logit]
        # ---------------------------------------------------------

        if logits.ndim != 1 or logits.shape[0] != 2:

            raise RuntimeError(
                f"Unexpected Dhwani output shape: "
                f"{logits.shape}"
            )

        # Numerically stable softmax

        shifted = logits - np.max(logits)

        exp_logits = np.exp(shifted)

        probabilities = (
            exp_logits /
            np.sum(exp_logits)
        )

        genuine_probability = float(
            probabilities[0]
        )

        synthetic_probability = float(
            probabilities[1]
        )

        return float(
            np.clip(
                synthetic_probability,
                0.0,
                1.0,
            )
        )

    def predict_with_details(
        self,
        audio: np.ndarray,
    ) -> dict:

        inp = self._prep(audio)

        outputs = self.session.run(
            [self.output_name],
            {
                self.input_name: inp
            },
        )

        logits = np.asarray(
            outputs[0],
            dtype=np.float32,
        ).squeeze()

        shifted = logits - np.max(logits)

        exp_logits = np.exp(shifted)

        probabilities = (
            exp_logits /
            np.sum(exp_logits)
        )

        return {
            "genuine_probability": float(
                probabilities[0]
            ),
            "synthetic_probability": float(
                probabilities[1]
            ),
            "logit_genuine": float(
                logits[0]
            ),
            "logit_synthetic": float(
                logits[1]
            ),
        }

    def predict_stream(
        self,
        windows: list[np.ndarray],
    ) -> list[float]:

        return [
            self.predict(window)
            for window in windows
        ]


_detector_singleton: DhwaniDetector | None = None


def get_dhwani_detector() -> DhwaniDetector:

    global _detector_singleton

    if _detector_singleton is None:

        _detector_singleton = DhwaniDetector()

    return _detector_singleton