from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import logging
from app.services.deepfake_service import DeepfakeUnavailable, analyze_deepfake
from app.services.risk_service import calculate_risk
from app.services.speaker_service import verify_speaker
from app.services.prosody_service import analyze_prosody
from app.services.prevention_service import trigger_prevention

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/analyze-stream")
async def websocket_analyze_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected for real-time analysis")
    # mod_audio_stream passes STREAM_EXTRA_HEADERS as HTTP headers
    call_metadata = {}
    for key, value in websocket.headers.items():
        if key.startswith("x-"):
            call_metadata[key] = value
            
    try:
        while True:
            # We expect the client (e.g., FreeSWITCH) to send metadata as text and audio as bytes
            message = await websocket.receive()
            
            if "text" in message:
                try:
                    meta = json.loads(message["text"])
                    call_metadata.update(meta)
                    logger.info(f"Received call metadata: {call_metadata}")
                except json.JSONDecodeError:
                    logger.warning("Received invalid text metadata")
                continue
                
            if "bytes" not in message:
                continue
                
            data = message["bytes"]
            
            if not data:
                continue

            try:
                # 1. Deepfake Model
                deepfake = analyze_deepfake("stream", data)
                deepfake_prob = deepfake["deepfake_probability"]
            except DeepfakeUnavailable:
                deepfake_prob = 0.0
                deepfake = {"deepfake_probability": 0.0, "available": False}
            except ValueError as e:
                logger.error(f"Error decoding audio chunk: {e}")
                await websocket.send_json({"error": "Invalid audio chunk"})
                continue
                
            # 2. Placeholders for other signals
            speaker_match = verify_speaker("stream", data)
            prosody_result = analyze_prosody("stream", data)
            prosody_risk = prosody_result["overall_prosody_risk"]
            context_risk = 0.5  # Default for live stream
            
            # 3. Risk Engine
            risk_result = calculate_risk(
                deepfake_prob=deepfake_prob,
                speaker_match=speaker_match,
                prosody_anomaly=prosody_risk,
                context_risk=context_risk,
            )
            
            prevention_action = trigger_prevention(risk_result["risk_score"], risk_result["risk_level"])
            
            response = {
                "signals": {
                    "deepfake_probability": deepfake_prob,
                    "speaker_match": speaker_match,
                    "prosody_analysis": prosody_result,
                    "context_risk": context_risk,
                },
                "deepfake_detail": deepfake,
                "risk_assessment": risk_result,
                "prevention_status": prevention_action,
                "metadata": call_metadata,
            }
            
            await websocket.send_json(response)
            
    except WebSocketDisconnect:
        logger.info("Client disconnected from stream")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
