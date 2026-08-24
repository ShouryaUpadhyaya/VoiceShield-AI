from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import audio

app = FastAPI(title="VoiceShield AI API")

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
