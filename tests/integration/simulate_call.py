"""Stream an audio file through the WebSocket as if it were a live call.

Sends real-time-paced PCM chunks (default 100 ms) rather than dumping the whole
file, so the server exercises the same buffering and windowing path a real
telephony gateway would drive.

    python tests/integration/simulate_call.py <audio> [--ws URL] [--speed N]

--speed 0 sends as fast as possible (useful in CI); --speed 1 is real time.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr
import websockets

SR = 16_000
CHUNK_MS = 100


async def simulate(path: Path, url: str, speed: float, chunk_ms: int) -> int:
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    audio = audio.mean(axis=1)
    if sr != SR:
        audio = soxr.resample(audio, sr, SR, quality="VHQ").astype(np.float32)

    chunk = int(SR * chunk_ms / 1000)
    total = int(np.ceil(audio.size / chunk))
    print(f"{path.name}: {audio.size/SR:.2f}s -> {total} chunks of {chunk_ms} ms")

    scores, worst = [], None
    async with websockets.connect(url, max_size=8 * 1024 * 1024) as ws:
        hello = json.loads(await ws.recv())
        print(f"connected · backend={hello.get('backend')} "
              f"window={hello.get('window_seconds')}s hop={hello.get('hop_seconds')}s\n")

        async def reader():
            nonlocal worst
            try:
                async for raw in ws:
                    m = json.loads(raw)
                    if m.get("type") == "session_closed":
                        return
                    if m.get("type") != "score":
                        continue
                    if m.get("status") == "DETECTOR_UNAVAILABLE":
                        print(f"  win {m['window_seq']:>3}  DETECTOR_UNAVAILABLE — no score emitted")
                        continue
                    r = m["risk_assessment"]
                    scores.append(r["risk_score"])
                    if worst is None or r["risk_score"] > worst["risk_assessment"]["risk_score"]:
                        worst = m
                    print(f"  t={m['audio_time_s']:>5.1f}s  win {m['window_seq']:>3}  "
                          f"spoof={m['signals']['deepfake_probability']:.3f}  "
                          f"risk={r['risk_score']:>3} {r['risk_level']:<6} "
                          f"{m['prevention_status']['status']:<20} "
                          f"({m['inference_ms']:.0f} ms)")
            except websockets.ConnectionClosed:
                pass

        task = asyncio.create_task(reader())
        for i in range(total):
            pcm = (np.clip(audio[i*chunk:(i+1)*chunk], -1, 1) * 32767).astype("<i2")
            await ws.send(pcm.tobytes())
            if speed > 0:
                await asyncio.sleep(chunk_ms / 1000.0 / speed)
        await ws.send(json.dumps({"type": "eof"}))
        await asyncio.wait_for(task, timeout=30)

    print("\n--- summary ---")
    if not scores:
        print("NO SCORES PRODUCED"); return 1
    print(f"windows scored : {len(scores)}")
    print(f"risk  min/mean/max : {min(scores)} / {sum(scores)/len(scores):.1f} / {max(scores)}")
    if worst:
        w = worst["risk_assessment"]
        print(f"peak risk  : {w['risk_score']} {w['risk_level']} -> {w['recommended_action']}")
        print(f"backend    : {worst.get('backend')}  validated={worst.get('validated')}")
        if worst.get("warning"):
            print(f"WARNING    : {worst['warning']}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", type=Path)
    ap.add_argument("--ws", default="ws://127.0.0.1:8000/api/analyze-stream")
    ap.add_argument("--speed", type=float, default=0.0, help="0 = as fast as possible, 1 = real time")
    ap.add_argument("--chunk-ms", type=int, default=CHUNK_MS)
    a = ap.parse_args()
    if not a.audio.exists():
        print(f"not found: {a.audio}"); sys.exit(1)
    sys.exit(asyncio.run(simulate(a.audio, a.ws, a.speed, a.chunk_ms)))
