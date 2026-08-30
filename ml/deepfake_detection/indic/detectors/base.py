"""The smallest interface that lets one backend be swapped for another.

Deliberately minimal. It exposes a single call and a single result type; anything a
particular model needs beyond 16 kHz mono audio is that model's own business and lives
inside its adapter. Neither backend knows the other exists, so either can be replaced
without touching the surrounding system.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Protocol

import numpy as np

SAMPLE_RATE = 16_000


@dataclass
class DetectionResult:
    """One decision, carrying enough provenance to be safe to log or compare.

    `model` and `model_version` are not decoration: two backends producing a bare float
    each would be indistinguishable in a log, and comparing them would be silent
    nonsense. `threshold` and `verdict` are None when the backend has no calibrated
    operating point -- a score without a threshold is not a decision, and this refuses
    to invent one.
    """

    fake_probability: float
    real_probability: float
    model: str
    model_version: str
    threshold: float | None = None
    verdict: str | None = None
    windows_scored: int = 1
    audio_seconds: float = 0.0
    latency_ms: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class Detector(Protocol):
    """Backends implement this and nothing more."""

    name: str
    version: str

    def predict(self, audio_16k_mono: np.ndarray) -> DetectionResult: ...
