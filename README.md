# VoiceShield AI

VoiceShield is an advanced real-time voice verification and deepfake detection system. It seamlessly integrates a robust Node.js media gateway, a high-performance FastAPI ML inference backend, and a modern Next.js frontend to monitor live telephony calls.

## Key Features
- **Real-Time Chunking**: The media gateway intercepts raw PCM telephony streams and forwards audio chunks asynchronously.
- **Dhwani & ECAPA Models**: Powerful PyTorch models evaluate deepfake probabilities and verify speaker enrollments.
- **Live Dashboard**: Watch chunk processing in real-time on the Next.js frontend via WebSocket integration.
- **PostgreSQL Persistence**: Comprehensive call records, raw chunks, and ML scores are securely saved for analysis.

## Setup

1. **Database & Backend**
   ```bash
   cd media-gateway
   npx prisma db push
   npx prisma generate
   npm install
   npm run dev
   ```
2. **ML Service**
   Run the ML backend from the `backend` directory with `PYTHONPATH=..` so it can find the `ml` models. Use the PyTorch extra index to install CUDA 12.6 correctly.
   ```bash
   # From the VoiceShield-AI root directory
   source .venv/bin/activate
   pip install --extra-index-url https://download.pytorch.org/whl/cu126 -r ml/requirements-torch.txt
   cd backend
   PYTHONPATH=.. uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
3. **Frontend Dashboard**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Architecture
See `docs/architecture_doc.md` for a comprehensive breakdown of the Media Pipeline and WebSocket interactions.

## Testing
Unit and integration tests are available. Run `npm run test` inside `media-gateway` to execute the full suite, including Prisma persistence and mock ML clients.
