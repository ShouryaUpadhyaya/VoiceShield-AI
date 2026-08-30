"""
Health and readiness endpoints for the ML service.

GET /health — process is alive
GET /ready  — models are loaded

The gateway checks /health to determine if ML is available.
The /ready endpoint reports per-model status so the operator
knows exactly which capabilities are functional.
"""
from __future__ import annotations

import time
import torch

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ml.adapters import dhwani as dhwani_adapter
from ml.adapters import deepfake as deepfake_adapter
from ml.adapters import speaker as speaker_adapter
from ml.adapters import prosody as prosody_adapter

health_router = APIRouter()

_startup_time = time.time()


def _detect_device() -> str:
    """Report the active compute device."""
    try:
        if torch.cuda.is_available():
            return f"cuda:{torch.cuda.get_device_name(0)}"
    except Exception:
        pass
    return "cpu"


@health_router.get("/health")
async def health():
    """Process alive check."""
    return {
        "status": "ok",
        "uptime_s": round(time.time() - _startup_time, 1),
        "service": "voiceshield-ml",
    }


@health_router.get("/ready")
async def ready():
    """Model readiness check."""
    models = {
        "dhwani":          dhwani_adapter.is_loaded(),
        "custom_deepfake": deepfake_adapter.is_loaded(),
        "speaker":         speaker_adapter.is_loaded(),
        "prosody":         prosody_adapter.is_loaded(),
    }

    model_versions = {
        "dhwani":          dhwani_adapter.get_version(),
        "custom_deepfake": deepfake_adapter.get_version(),
        "speaker":         speaker_adapter.get_version(),
        "prosody":         prosody_adapter.get_version(),
    }

    any_loaded = any(models.values())
    status = "ready" if any_loaded else "no_models"

    return JSONResponse(
        status_code=200 if any_loaded else 503,
        content={
            "status": status,
            "device": _detect_device(),
            "models": models,
            "model_versions": model_versions,
            "uptime_s": round(time.time() - _startup_time, 1),
        },
    )
