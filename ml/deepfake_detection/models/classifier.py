"""Model factory — one place that maps a config name to an architecture."""

from __future__ import annotations

import torch.nn as nn

from ml.deepfake_detection.models.baseline_model import LFCCBaseline
from ml.deepfake_detection.models.fusion_model import FusionSpoofDetector
from ml.deepfake_detection.models.ssl_model import SSLSpoofDetector

REGISTRY = {
    "lfcc_baseline": LFCCBaseline,
    "ssl": SSLSpoofDetector,
    "fusion": FusionSpoofDetector,
}


def build_model(name: str, **kwargs) -> nn.Module:
    if name not in REGISTRY:
        raise ValueError(f"unknown model {name!r}; available: {sorted(REGISTRY)}")
    return REGISTRY[name](**kwargs)
