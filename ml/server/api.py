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
from ml.pipeline.fusion import get_weights, set_weights
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

api_router = APIRouter(prefix="/api")

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
    return {"success": True, "weights": get_weights(), "calibrated": False,
            "policy": "sih-evidence-v1", "score_kind": "synthetic_audio_evidence"}

@api_router.put("/config/fusion")
async def update_fusion_config(payload: dict):
    try:
        weights = set_weights(payload.get("weights"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "weights": weights, "calibrated": False}


@api_router.post("/inference/pipeline")
async def run_pipeline(audio: UploadFile = File(...)):
    file_bytes = await audio.read()
    
    max_mb = int(os.environ.get("MAX_TEST_AUDIO_MB", "25"))
    if len(file_bytes) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum allowed size ({max_mb} MB).")
        
    audio_16k, duration_sec = load_audio_file(file_bytes)
    
    request_id = str(uuid.uuid4())
    
    # Run full inference orchestrator (which runs all loaded models safely)
    if duration_sec > 60:
        raise HTTPException(status_code=400, detail="Pipeline uploads are limited to 60 seconds. Stream longer recordings through the gateway.")
    from ml.pipeline.pooling import pool_responses
    windows = []
    for sequence, start in enumerate(range(0, max(1, len(audio_16k)), 48000)):
        result = await run_in_threadpool(run_inference, audio_16k[start:start+48000], session_id=request_id, sequence=sequence)
        windows.append(build_score_response(request_id, sequence, start // 16, result))
    score_res = pool_responses(windows)
    
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

from fastapi import Form

@api_router.post("/speaker/enroll")
async def enroll_speaker_api(speaker_id: str = Form(...), audio: UploadFile = File(...)):
    file_bytes = await audio.read()
    max_mb = int(os.environ.get("MAX_TEST_AUDIO_MB", "25"))
    if len(file_bytes) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum allowed size ({max_mb} MB).")
        
    audio_16k, duration_sec = load_audio_file(file_bytes)
    
    if not speaker_adapter.is_loaded():
        raise HTTPException(status_code=503, detail="Speaker Verification model is unavailable.")
        
    success = speaker_adapter.enroll_speaker(speaker_id, audio_16k)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to enroll speaker.")
        
    return {"success": True, "speaker_id": speaker_id, "duration_sec": round(duration_sec, 2)}

@api_router.post("/speaker/enroll-directory")
def enroll_directory_api(payload: dict):
    directory_path = payload.get("directory_path")
    if not directory_path:
        raise HTTPException(status_code=400, detail="directory_path is required.")
        
    if not speaker_adapter.is_loaded():
        raise HTTPException(status_code=503, detail="Speaker Verification model is unavailable.")
        
    result = speaker_adapter.enroll_directory(directory_path)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    return result
