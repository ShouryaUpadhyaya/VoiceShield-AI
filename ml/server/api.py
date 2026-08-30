import io
import os
import time
import uuid
import logging
from typing import Any

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

import numpy as np
import librosa

from ml.adapters import dhwani as dhwani_adapter
from ml.adapters import deepfake as deepfake_adapter
from ml.adapters import speaker as speaker_adapter
from ml.adapters import prosody as prosody_adapter
from ml.adapters import indic as indic_adapter

from ml.pipeline.inference import run_inference
from ml.pipeline.results import build_score_response
from ml.common.constants import SAMPLE_RATE

logger = logging.getLogger(__name__)

api_router = APIRouter(prefix="/api")

# In-memory fusion weights store
fusion_config = {
    "indic": float(os.environ.get("FUSION_INDIC_WEIGHT", "0.45")),
    "dhwani": float(os.environ.get("FUSION_DHWANI_WEIGHT", "0.20")),
    "customDeepfake": float(os.environ.get("FUSION_CUSTOM_WEIGHT", "0.20")),
    "prosody": float(os.environ.get("FUSION_PROSODY_WEIGHT", "0.15"))
}

def load_audio_file(file_bytes: bytes) -> tuple[np.ndarray, float]:
    """Load audio bytes into 16kHz mono float32 numpy array and get duration."""
    try:
        # librosa can load from file-like object using soundfile backend
        audio, sr = librosa.load(io.BytesIO(file_bytes), sr=SAMPLE_RATE, mono=True)
        duration_sec = len(audio) / sr
        return audio, duration_sec
    except Exception as e:
        logger.error(f"Error decoding audio: {e}")
        raise HTTPException(status_code=400, detail="Invalid audio format or corrupted file. Supported formats: WAV, MP3, FLAC, OGG, M4A.")

@api_router.get("/config/fusion")
async def get_fusion_config():
    return {"success": True, "weights": fusion_config}

@api_router.put("/config/fusion")
async def update_fusion_config(payload: dict):
    weights = payload.get("weights", {})
    
    # Validation
    if not isinstance(weights, dict):
        raise HTTPException(status_code=400, detail="weights must be an object")
    
    supported_models = {"indic", "dhwani", "customDeepfake", "prosody"}
    
    total = 0.0
    for k, v in weights.items():
        if k not in supported_models:
            raise HTTPException(status_code=400, detail=f"Unsupported model: {k}")
        if not isinstance(v, (int, float)) or v < 0 or v > 100: # Could be 0-1 or 0-100, assuming 0-1 based on initial config
             raise HTTPException(status_code=400, detail=f"Invalid weight for {k}")
        total += float(v)
        
    if not (0.99 <= total <= 1.01):
        raise HTTPException(status_code=400, detail=f"Weights must sum to 1.0 (current total: {total})")
        
    for k in supported_models:
        if k in weights:
            fusion_config[k] = float(weights[k])
            
    # Also update os.environ for compatibility with existing build_score_response
    os.environ["FUSION_INDIC_WEIGHT"] = str(fusion_config.get("indic", 0.45))
    os.environ["FUSION_DHWANI_WEIGHT"] = str(fusion_config.get("dhwani", 0.20))
    os.environ["FUSION_CUSTOM_WEIGHT"] = str(fusion_config.get("customDeepfake", 0.20))
    os.environ["FUSION_PROSODY_WEIGHT"] = str(fusion_config.get("prosody", 0.15))
    
    return {"success": True, "weights": fusion_config}


@api_router.post("/inference/pipeline")
async def run_pipeline(audio: UploadFile = File(...)):
    file_bytes = await audio.read()
    
    max_mb = int(os.environ.get("MAX_TEST_AUDIO_MB", "25"))
    if len(file_bytes) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum allowed size ({max_mb} MB).")
        
    audio_16k, duration_sec = load_audio_file(file_bytes)
    
    request_id = str(uuid.uuid4())
    
    # Run full inference orchestrator (which runs all loaded models safely)
    result = run_inference(audio_16k, session_id=request_id, sequence=0)
    
    # build_score_response will apply fusion weights (pulling from os.environ which we keep synced)
    score_res = build_score_response(
        session_id=request_id,
        sequence=0,
        timestamp_ms=0,
        inference_result=result
    )
    
    return {
        "requestId": request_id,
        "status": "success",
        "latencyMs": score_res["inference_ms"],
        "input": {
            "filename": audio.filename,
            "durationSec": round(duration_sec, 2),
            "sampleRate": SAMPLE_RATE,
            "channels": 1
        },
        "result": score_res
    }

@api_router.post("/inference/{model_name}")
async def run_single_model(model_name: str, audio: UploadFile = File(...)):
    file_bytes = await audio.read()
    max_mb = int(os.environ.get("MAX_TEST_AUDIO_MB", "25"))
    if len(file_bytes) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum allowed size ({max_mb} MB).")
        
    audio_16k, duration_sec = load_audio_file(file_bytes)
    
    t0 = time.perf_counter()
    model_res = None
    version = "unavailable"
    
    try:
        if model_name == "indic":
            if not indic_adapter.is_loaded():
                raise HTTPException(status_code=503, detail="Indic Detector is unavailable.")
            model_res = indic_adapter.run(audio_16k)
            version = indic_adapter.get_version()
        elif model_name == "dhwani":
            if not dhwani_adapter.is_loaded():
                raise HTTPException(status_code=503, detail="Dhwani is unavailable.")
            model_res = dhwani_adapter.run(audio_16k)
            version = dhwani_adapter.get_version()
        elif model_name == "custom-deepfake":
            if not deepfake_adapter.is_loaded():
                raise HTTPException(status_code=503, detail="Custom Deepfake is unavailable.")
            model_res = deepfake_adapter.run(audio_16k)
            version = deepfake_adapter.get_version()
        elif model_name == "prosody":
            if not prosody_adapter.is_loaded():
                raise HTTPException(status_code=503, detail="Prosody Analyzer is unavailable.")
            model_res = prosody_adapter.run(audio_16k)
            version = prosody_adapter.get_version()
        elif model_name == "speaker":
            if not speaker_adapter.is_loaded():
                raise HTTPException(status_code=503, detail="Speaker Verification is unavailable.")
            model_res = speaker_adapter.run(audio_16k)
            version = speaker_adapter.get_version()
        else:
            raise HTTPException(status_code=404, detail=f"Unknown model: {model_name}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running {model_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Inference error in {model_name}: {str(e)}")
        
    latency_ms = (time.perf_counter() - t0) * 1000.0
    
    return {
        "requestId": str(uuid.uuid4()),
        "model": model_name,
        "modelVersion": version,
        "status": "success",
        "latencyMs": round(latency_ms, 2),
        "input": {
            "filename": audio.filename,
            "durationSec": round(duration_sec, 2),
            "sampleRate": SAMPLE_RATE,
            "channels": 1
        },
        "result": model_res
    }

@api_router.get("/models")
async def get_models():
    """Detailed model status endpoint."""
    return {
        "models": {
            "indic": {
                "status": "ready" if indic_adapter.is_loaded() else "unavailable",
                "version": indic_adapter.get_version(),
                "reason": "Weights loaded" if indic_adapter.is_loaded() else "Weights missing or failed to load"
            },
            "dhwani": {
                "status": "ready" if dhwani_adapter.is_loaded() else "unavailable",
                "version": dhwani_adapter.get_version(),
                "reason": "Weights loaded" if dhwani_adapter.is_loaded() else "Weights missing or failed to load"
            },
            "customDeepfake": {
                "status": "ready" if deepfake_adapter.is_loaded() else "unavailable",
                "version": deepfake_adapter.get_version(),
                "reason": "Weights loaded" if deepfake_adapter.is_loaded() else "Weights missing or failed to load"
            },
            "prosody": {
                "status": "ready" if prosody_adapter.is_loaded() else "unavailable",
                "version": prosody_adapter.get_version(),
                "reason": "Successfully initialized" if prosody_adapter.is_loaded() else "Failed to initialize"
            },
            "speaker": {
                "status": "ready" if speaker_adapter.is_loaded() else "unavailable",
                "version": speaker_adapter.get_version(),
                "reason": "Weights loaded" if speaker_adapter.is_loaded() else "Weights missing or failed to load"
            }
        }
    }
