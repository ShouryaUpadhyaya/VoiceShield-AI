# VoiceShield-AI Dashboard

This is the Next.js frontend for the VoiceShield-AI media gateway. It provides a real-time observability dashboard for tracking live active calls, buffer statistics, and chunking invariants, as well as a historical data view to listen to downloaded PCM/WAV recordings.

## Getting Started

First, ensure the media gateway backend (Node.js) is running and PostgreSQL is up.

```bash
cd ../media-gateway
docker compose up -d postgres
npx prisma db push
npm run dev
```

Next, in a separate terminal, install the frontend dependencies and start the Next.js development server:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Architecture

- **Next.js**: App Router, Server/Client components.
- **Zustand**: Manages the high-frequency real-time WebSocket state from the media gateway (`/dashboard` WebSocket endpoint).
- **TanStack Query**: Manages polling and fetching of historical data (`/api/calls`, `/api/stats`).
- **Tailwind CSS**: Styling and layout.

## Environment Variables

You can configure the backend target by setting the `NEXT_PUBLIC_GATEWAY_URL` environment variable. By default, it connects to `http://localhost:8010`.

```bash
# .env.local
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8010
```
