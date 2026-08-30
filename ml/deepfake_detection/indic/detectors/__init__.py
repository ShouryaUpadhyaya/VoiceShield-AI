"""Selectable detector backends.

Selection happens here, at configuration level -- neither backend imports or knows about
the other, so either can be replaced without touching the surrounding system.
"""

from .base import Detector, DetectionResult, SAMPLE_RATE

BACKENDS = ("voiceshield", "dhwani")
DEFAULT_BACKEND = "voiceshield"          # the model this project adapted

DEFAULT_VOICESHIELD_CKPT = "checkpoints_f5_iv15/best_model.pth"
# iv15 is the best all-round model: A 1.68%, B 25.49%, C 9.76%, D AUC 0.533,
# FLEURS false-accusation 16.2% against v1's 26.2%. It was trained on TRIMMED
# audio and the backend now reads that contract from the checkpoint, so pointing
# this at a differently-trained checkpoint stays correct automatically.
DEFAULT_DHWANI_ONNX = ("/home/aayushdwivedi/Projects/VoiceShield-AI/"
                       "data/external_models/dhwani/best_model.onnx")


def build_detector(backend: str = DEFAULT_BACKEND, **kwargs) -> Detector:
    """Construct one backend by name. Imports are lazy so that selecting VoiceShield
    does not require onnxruntime, and selecting Dhwani does not require torch."""
    backend = (backend or DEFAULT_BACKEND).lower()
    if backend == "voiceshield":
        from .voiceshield_backend import VoiceShieldDetector
        return VoiceShieldDetector(kwargs.pop("checkpoint", DEFAULT_VOICESHIELD_CKPT), **kwargs)
    if backend == "dhwani":
        from .dhwani_backend import DhwaniDetector
        return DhwaniDetector(kwargs.pop("model_path", DEFAULT_DHWANI_ONNX), **kwargs)
    raise ValueError(f"unknown backend {backend!r}; choose from {BACKENDS}")


__all__ = ["Detector", "DetectionResult", "SAMPLE_RATE", "BACKENDS",
           "DEFAULT_BACKEND", "build_detector"]
