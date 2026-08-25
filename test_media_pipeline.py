import asyncio
import json
import logging
import socket
import time
from datetime import datetime
from typing import List

import numpy as np
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

# Setup custom logger that also broadcasts to SSE
class SSELogger:
    def __init__(self):
        self.clients: List[asyncio.Queue] = []
        self.calls = {}

    def log_event(self, event: dict):
        # Format the event as a JSON string
        timestamp = datetime.now().strftime("%H:%M:%S")
        event["timestamp"] = timestamp
        log_entry = json.dumps(event)
        print(log_entry, flush=True)
        for client in self.clients:
            client.put_nowait(log_entry)

    def log(self, message: str):
        self.log_event({"type": "log", "message": message})

    async def add_client(self):
        q = asyncio.Queue()
        self.clients.append(q)
        return q

    def remove_client(self, q):
        if q in self.clients:
            self.clients.remove(q)

sse_logger = SSELogger()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/logs")
async def get_logs(request: Request):
    async def event_generator():
        q = await sse_logger.add_client()
        try:
            while True:
                if await request.is_disconnected():
                    break
                log_entry = await q.get()
                yield {"data": log_entry}
        finally:
            sse_logger.remove_client(q)
            
    return EventSourceResponse(event_generator())

@app.get("/api/calls")
async def get_calls():
    return {"calls": sse_logger.calls}

@app.websocket("/api/analyze-stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    call_metadata = {}
    for key, value in websocket.headers.items():
        if key.startswith("x-"):
            call_metadata[key] = value
            
    call_id = call_metadata.get("x-call_id", "unknown")
    if call_id not in sse_logger.calls:
        sse_logger.calls[call_id] = {
            "id": call_id,
            "status": "active",
            "metadata": call_metadata,
            "total_bytes": 0,
            "start_time": datetime.now().isoformat()
        }

    sse_logger.log_event({"type": "call_start", "call": sse_logger.calls[call_id]})
    sse_logger.log(f"WebSocket connected from FreeSWITCH for Call {call_id}.")
    
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
                
            if "text" in message and message.get("text"):
                try:
                    meta = json.loads(message["text"])
                    call_metadata.update(meta)
                    sse_logger.calls[call_id]["metadata"] = call_metadata
                    sse_logger.log_event({"type": "metadata_update", "call_id": call_id, "metadata": call_metadata})
                except Exception as e:
                    sse_logger.log(f"Failed to parse metadata text: {e}")
                continue
                
            if "bytes" in message and message.get("bytes"):
                chunk = message["bytes"]
                bytes_len = len(chunk)
                sse_logger.calls[call_id]["total_bytes"] += bytes_len
                
                rms = 0.0
                vad = False
                spectrum = []
                
                try:
                    audio_data = np.frombuffer(chunk, dtype=np.int16)
                    if len(audio_data) > 0:
                        rms = float(np.sqrt(np.mean(np.square(audio_data.astype(np.float32)))))
                        vad = bool(rms > 500)
                        fft_out = np.abs(np.fft.rfft(audio_data))
                        bins = 32
                        if len(fft_out) >= bins:
                            split = np.array_split(fft_out, bins)
                            spectrum = [float(np.mean(b)) for b in split]
                except Exception as dsp_e:
                    sse_logger.log(f"DSP Error: {dsp_e}")
                
                # Emit audio chunk event for graph
                sse_logger.log_event({
                    "type": "audio_chunk",
                    "call_id": call_id,
                    "bytes_received": bytes_len,
                    "total_bytes": sse_logger.calls[call_id]["total_bytes"],
                    "rms": rms,
                    "vad": vad,
                    "spectrum": spectrum
                })
                
    except WebSocketDisconnect:
        pass
        sse_logger.calls[call_id]["status"] = "ended"
        sse_logger.calls[call_id]["end_time"] = datetime.now().isoformat()
        sse_logger.log_event({"type": "call_end", "call_id": call_id, "call": sse_logger.calls[call_id]})
    except Exception as e:
        sse_logger.log(f"WebSocket Error: {e}")

async def run_sip_test():
    # Wait for FreeSWITCH to be fully up
    await asyncio.sleep(5)
    sse_logger.log("Initiating Automated SIP Test to FreeSWITCH...")
    
    sip_invite = """INVITE sip:test_call@freeswitch SIP/2.0
Via: SIP/2.0/UDP 127.0.0.1:5061;branch=z9hG4bK-test1
Max-Forwards: 70
To: <sip:test_call@freeswitch>
From: <sip:tester@127.0.0.1>;tag=testtag1
Call-ID: test-call-id-12345@127.0.0.1
CSeq: 1 INVITE
Contact: <sip:tester@127.0.0.1:5061>
Content-Type: application/sdp
Content-Length: 129

v=0
o=user1 53655765 2353687637 IN IP4 127.0.0.1
s=-
c=IN IP4 127.0.0.1
t=0 0
m=audio 6000 RTP/AVP 0
a=rtpmap:0 PCMU/8000
""".replace('\n', '\r\n')

    loop = asyncio.get_running_loop()
    
    class SIPProtocol(asyncio.DatagramProtocol):
        def __init__(self):
            self.transport = None
            self.call_active = False

        def connection_made(self, transport):
            self.transport = transport
            transport.sendto(sip_invite.encode('utf-8'))
            sse_logger.log("Sent SIP INVITE to freeswitch:5060")

        def datagram_received(self, data, addr):
            response = data.decode('utf-8', errors='ignore')
            if "200 OK" in response and not self.call_active:
                self.call_active = True
                sse_logger.log("Received 200 OK. Sending ACK.")
                
                ack = """ACK sip:test_call@freeswitch SIP/2.0
Via: SIP/2.0/UDP 127.0.0.1:5061;branch=z9hG4bK-test1-ack
Max-Forwards: 70
To: <sip:test_call@freeswitch>;tag=REPLACE_TAG
From: <sip:tester@127.0.0.1>;tag=testtag1
Call-ID: test-call-id-12345@127.0.0.1
CSeq: 1 ACK
Contact: <sip:tester@127.0.0.1:5061>
Content-Length: 0
""".replace('\n', '\r\n')
                self.transport.sendto(ack.encode('utf-8'))
                sse_logger.log("Call is now active. Audio stream should begin.")

    try:
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: SIPProtocol(),
            local_addr=('0.0.0.0', 5061),
            remote_addr=('freeswitch', 5060)
        )
        
        # Let the call run for 15 seconds
        await asyncio.sleep(15)
        
        if protocol.call_active:
            bye = """BYE sip:test_call@freeswitch SIP/2.0
Via: SIP/2.0/UDP 127.0.0.1:5061;branch=z9hG4bK-test1-bye
Max-Forwards: 70
To: <sip:test_call@freeswitch>
From: <sip:tester@127.0.0.1>;tag=testtag1
Call-ID: test-call-id-12345@127.0.0.1
CSeq: 2 BYE
Content-Length: 0
""".replace('\n', '\r\n')
            transport.sendto(bye.encode('utf-8'))
            sse_logger.log("Sent SIP BYE. Call ended.")
        
        transport.close()
    except Exception as e:
        sse_logger.log(f"SIP Test Error: {e}")

async def heartbeat():
    while True:
        sse_logger.log("Heartbeat: Server is alive and waiting for connections...")
        await asyncio.sleep(10)

@app.on_event("startup")
async def startup_event():
    sse_logger.log("Media Pipeline Tester starting up on port 8005...")
    asyncio.create_task(run_sip_test())
    asyncio.create_task(heartbeat())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8005)
