"""
Entry point for the VoiceShield ML service.

Loads all models into memory at startup, then starts the Uvicorn server.
If a model fails to load (e.g. missing weights), it is marked as UNAVAILABLE,
but the service still starts.

Usage:
  python -m ml.server.main
"""
from __future__ import annotations

import logging
import os

import uvicorn
from dotenv import load_dotenv

# Configure logging before importing other modules
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

from ml.adapters import dhwani as dhwani_adapter
from ml.adapters import deepfake as deepfake_adapter
from ml.adapters import speaker as speaker_adapter
from ml.adapters import prosody as prosody_adapter
from ml.adapters import indic as indic_adapter


def _load_all_models():
    """Load all model singletons into memory."""
    logger.info("ML_STARTUP", extra={"detail": "Loading models..."})

    # Dhwani ONNX
    dhwani_ok = dhwani_adapter.load_dhwani()
    if not dhwani_ok:
        logger.warning("Dhwani model unavailable.")

    # Custom Deepfake (PyTorch)
    df_ok = deepfake_adapter.load_deepfake()
    if not df_ok:
        logger.warning("Custom deepfake model unavailable.")

    # Indic Deepfake
    indic_ok = indic_adapter.load_indic()
    if not indic_ok:
        logger.warning("Indic model unavailable.")

    # ECAPA Speaker (PyTorch/SpeechBrain)
    speaker_ok = speaker_adapter.load_speaker()
    if not speaker_ok:
        logger.warning("Speaker verification unavailable.")

    # Prosody (Parselmouth)
    prosody_ok = prosody_adapter.load_prosody()
    if not prosody_ok:
        logger.warning("Prosody analysis unavailable.")

    logger.info(
        "ML_MODELS_LOADED",
        extra={
        "dhwani": dhwani_ok,
            "custom_deepfake": df_ok,
            "indic": indic_ok,
            "speaker": speaker_ok,
            "prosody": prosody_ok,
        },
    )


def main():
    load_dotenv()
    
    _load_all_models()
    
    host = os.getenv("ML_HOST", "0.0.0.0")
    port = int(os.getenv("ML_PORT", "8011"))

    logger.info("ML_SERVER_START", extra={"host": host, "port": port})
    
    # Run server
    uvicorn.run(
        "ml.server.app:app",
        host=host,
        port=port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
