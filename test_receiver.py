import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.websocket("/api/analyze-stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected for Role 3 Test")
    
    total_bytes = 0
    call_metadata = {}
    
    try:
        while True:
            message = await websocket.receive()
            
            if "text" in message:
                logger.info(f"Received text message: {message['text']}")
                try:
                    meta = json.loads(message["text"])
                    call_metadata.update(meta)
                    logger.info(f"Metadata parsed: {call_metadata}")
                except Exception as e:
                    logger.error(f"Failed to parse metadata: {e}")
                continue
                
            if "bytes" in message:
                chunk = message["bytes"]
                total_bytes += len(chunk)
                if total_bytes % 160000 == 0:  # Log every ~5 seconds of 16kHz L16 audio
                    logger.info(f"Received {total_bytes} bytes of audio so far...")
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected. Total bytes received: {total_bytes}")
        logger.info(f"Session Metadata was: {call_metadata}")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    logger.info("Starting Role 3 Test WebSocket Receiver on ws://0.0.0.0:8005/api/analyze-stream")
    uvicorn.run(app, host="0.0.0.0", port=8005)
