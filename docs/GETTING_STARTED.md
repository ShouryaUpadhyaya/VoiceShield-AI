# VoiceShield-AI: Getting Started

This guide provides a complete, step-by-step tutorial to run the full VoiceShield-AI stack locally. The system consists of four primary components:
1. **PostgreSQL Database**: Stores call metadata, chunk records, and ML fusion results.
2. **Python ML Service**: Hosts the Dhwani, Custom Deepfake, Prosody, ECAPA Speaker, and Indic detectors.
3. **Node.js Media Gateway**: Accepts WebSocket audio streams, persists data, and routes audio to the ML service.
4. **Next.js Frontend Dashboard**: Visualizes real-time metrics, chunk fusion scores, and the ML pipeline status.

---

## 1. Prerequisites
Ensure you have the following installed on your machine:
- Node.js (v18+)
- Python (v3.10+)
- PostgreSQL (or Docker/Podman to run a container)
- Git (with Git LFS installed via `git lfs install`)

First, ensure you have pulled the large model weights properly:
```bash
git lfs pull
```

---

## 2. Start PostgreSQL
You need a running PostgreSQL instance. If you have Docker installed, the easiest way is:
```bash
docker run --name voiceshield-db -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=admin -e POSTGRES_DB=voiceshield -p 5432:5432 -d postgres
```
Alternatively, if you run PostgreSQL locally, ensure you create a database named `voiceshield` with the credentials `admin:admin`.

---

## 3. Run the Media Gateway
The Node.js Media Gateway manages the database and handles incoming audio streams.

1. Navigate to the gateway directory:
   ```bash
   cd media-gateway
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Set up your environment file:
   ```bash
   cp .env.example .env
   ```
   *(Ensure `DATABASE_URL` in `.env` points to `postgresql://admin:admin@localhost:5432/voiceshield`)*
4. Initialize the database schema:
   ```bash
   npx prisma db push
   npx prisma generate
   ```
5. Start the gateway server:
   ```bash
   npm run dev
   ```
The gateway will start on `http://localhost:8010` (REST) and `ws://localhost:8010` (WebSockets).

---

## 4. Run the Python ML Service
The ML service loads the models and performs real-time inference on the audio chunks.

1. Open a **new terminal tab** at the **root** of the repository (`/Programming/VoiceShield-AI`).
2. Create and activate a virtual environment (if you haven't already):
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r ml/requirements.txt
   ```
4. Set up your environment file:
   ```bash
   cp ml/.env.example ml/.env
   ```
5. Start the ML service (run this from the root of the repository!):
   ```bash
   python -m ml.server.main
   ```
The service will start loading the Dhwani, Custom Deepfake, ECAPA Speaker, Prosody, and Indic models into memory. Once finished, it will listen on `ws://0.0.0.0:8011/`.

---

## 5. Run the Frontend Dashboard
The frontend is a Next.js application that visualizes the pipeline and scores in real time.

1. Open a **third terminal tab** and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the Next.js development server:
   ```bash
   npm run dev
   ```
4. Open your browser and navigate to: **[http://localhost:3000](http://localhost:3000)**

---

## 6. Send Test Audio
To verify that everything is connected and working, you can simulate a live call using the provided test script.

1. Ensure all three services (Gateway, ML, Frontend) are running.
2. In the `media-gateway` directory, run:
   ```bash
   npm run send-test
   ```
3. Look at your [Frontend Dashboard](http://localhost:3000). You will see a "Live Session" appear, with chunks streaming in, the ML models scoring each chunk, and the new **Indic Detector** and **AI Fusion Score** updating in real time!
