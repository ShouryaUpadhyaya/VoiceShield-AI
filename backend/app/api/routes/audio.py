from fastapi import APIRouter, UploadFile, File
from app.services.deepfake_service import analyze_deepfake
from app.services.speaker_service import verify_speaker
from app.services.prosody_service import analyze_prosody
from app.services.risk_service import calculate_risk
from app.services.prevention_service import trigger_prevention

router = APIRouter()

@router.post("/analyze/audio")
async def analyze_audio(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    
    # 1. Deepfake Model
    deepfake_prob = analyze_deepfake(file.filename, audio_bytes)
    
    # 2. Speaker Verification
    speaker_match = verify_speaker(file.filename, audio_bytes)
    
    # 3. Prosody & Behavioral Analysis
    prosody_result = analyze_prosody(file.filename, audio_bytes)
    prosody_risk = prosody_result["overall_prosody_risk"]
    
    # 4. Contextual Risk
    context_risk = 0.85 if "transfer" in file.filename.lower() else 0.4
    
    # 5. Risk Fusion Engine
    risk_result = calculate_risk(
        deepfake_prob=deepfake_prob,
        speaker_match=speaker_match,
        prosody_anomaly=prosody_risk,
        context_risk=context_risk
    )
    
    # 6. Prevention Engine
    prevention_action = trigger_prevention(risk_result["risk_score"], risk_result["risk_level"])
    
    return {
        "filename": file.filename,
        "signals": {
            "deepfake_probability": deepfake_prob,
            "speaker_match": speaker_match,
            "prosody_analysis": prosody_result,
            "context_risk": context_risk
        },
        "risk_assessment": risk_result,
        "prevention_status": prevention_action
    }
