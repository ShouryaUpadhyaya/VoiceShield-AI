"""Offline smoke check through real FastAPI HTTP/WebSocket routes and models."""
import argparse
import io
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import soundfile as sf
import soxr
import torch
from fastapi.testclient import TestClient
from ml.server.app import app


def wav(y):
    buffer = io.BytesIO()
    sf.write(buffer, y, 16000, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    torch.set_num_threads(2)
    rows = json.loads((ROOT / "docs/research/validation/live_audit.json").read_text())["records"]
    row = next(r for r in rows if r["label"] == 1 and r["set"] == "internal")
    y, sr = sf.read(args.corpus_root / row["path"], dtype="float32", always_2d=True)
    y = y.mean(axis=1)
    if sr != 16000:
        y = soxr.resample(y, sr, 16000).astype(np.float32)
    y = y[:48000]
    with TestClient(app) as client:
        ready = client.get('/ready')
        assert ready.status_code == 200 and all(ready.json()['models'].values())
        single = client.post('/api/inference/pipeline', files={'audio': ('sample.wav', wav(y), 'audio/wav')})
        assert single.status_code == 200, single.text
        assert single.json()['result']['risk']['score'] is not None
        mixed = client.post('/api/inference/pipeline', files={'audio': ('mixed.wav', wav(np.r_[np.zeros(48000), y]), 'audio/wav')})
        assert mixed.status_code == 200, mixed.text
        assert mixed.json()['result']['call_summary']['unscored_windows'] == 1
        stream_results = []
        with client.websocket_connect('/') as websocket:
            for sequence, source in enumerate([y, np.zeros(48000, dtype=np.float32)]):
                pcm = (np.clip(soxr.resample(source, 16000, 48000), -1, 1) * 32767).astype('<i2').tobytes()
                websocket.send_json({'type': 'audio.chunk', 'session_id': 'service-smoke', 'sequence': sequence,
                                     'timestamp_ms': sequence*3000, 'duration_ms': len(pcm)//96,
                                     'sample_rate': 48000, 'channels': 1, 'encoding': 'pcm_s16le', 'bytes': len(pcm)})
                websocket.send_bytes(pcm)
                response = websocket.receive_json()
                assert response['type'] == 'score', response
                assert not response['model_errors']
                stream_results.append(response)
        assert stream_results[0]['risk']['score'] is not None
        assert stream_results[1]['risk']['score'] is None
        from ml.adapters import speaker
        first, second = speaker._embedder.embed(y), speaker._embedder.embed(y)
        output = {'passed': True, 'path': row['path'], 'ready': ready.json(),
                  'http_single': single.json(), 'http_multiwindow': mixed.json(), 'websocket': stream_results,
                  'speaker_smoke': {'dimension': int(first.size), 'finite': bool(np.isfinite(first).all()),
                                    'repeat_cosine': speaker._cosine_similarity(first, second),
                                    'identity_accuracy_validated': False},
                  'limitations': ['In-process real-model service test; does not exercise PostgreSQL, browser or physical Android capture.']}
    args.out.write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    print('Real-model HTTP, multiwindow upload and WebSocket smoke checks passed.')


if __name__ == '__main__':
    main()
