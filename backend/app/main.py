import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audio
from app.services.deepfake_service import warm_up

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the model once, at startup. Doing it lazily on the first request
    # would make that request take ~10s and skew every latency measurement.
    app.state.deepfake_ready = warm_up()
    yield


app = FastAPI(title="VoiceShield AI API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(audio.router, prefix="/api")


@app.get("/")
def read_root():
    return {"message": "VoiceShield AI Backend is running."}


@app.get("/health")
def health():
    """Surfaces whether the detector is actually loaded, so a degraded
    deployment is visible instead of silently scoring everything as genuine."""
    from app.services.deepfake_service import get_predictor

    predictor = get_predictor()
    return {
        "status": "ok",
        "deepfake_model": {
            "loaded": predictor is not None,
            "checkpoint": predictor.checkpoint_path.name if predictor else None,
            "dev_eer": predictor.dev_eer if predictor else None,
            "device": predictor.device if predictor else None,
        },
    }
