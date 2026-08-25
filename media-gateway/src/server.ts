/**
 * Media Gateway Server
 *
 * Entry point: HTTP server (health endpoint) + WebSocket server (audio ingestion).
 *
 * Architecture:
 *   Audio Source (CallVault / FreeSWITCH / synthetic)
 *       ↓ WebSocket
 *   This Gateway (session → chunker → ML client)
 *       ↓ WebSocket
 *   ML Service
 */

import http from 'node:http';
import { WebSocketServer, WebSocket } from 'ws';
import { loadConfig, type GatewayConfig } from './config.js';
import { parseMessage, ProtocolError } from './protocol.js';
import { SessionManager, type AudioSession } from './session.js';
import { MlClient } from './ml-client.js';
import { DebugRecorder } from './debug-recorder.js';
import { logger, setLogLevel } from './logger.js';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Define __dirname for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ── Bootstrap ──────────────────────────────────────────────────────

const config = loadConfig();
setLogLevel(config.logLevel);

const sessionManager = new SessionManager(config.chunkDurationSec);
const mlClient = new MlClient(config.mlWsUrl);
const debugRecorder = config.saveDebugAudio ? new DebugRecorder(config.debugAudioDir) : null;

// ── HTTP Server (health endpoint) ──────────────────────────────────

const httpServer = http.createServer((req, res) => {
  if (req.method === 'GET' && req.url === '/health') {
    const health = {
      status: 'ok',
      mlConnected: mlClient.isConnected,
      activeSessions: sessionManager.activeCount,
      sessions: sessionManager.getSessionInfos(),
      uptime: process.uptime(),
    };
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(health, null, 2));
    return;
  }

  if (req.method === 'GET' && (req.url === '/' || req.url === '/index.html')) {
    const indexPath = path.join(__dirname, '..', 'public', 'index.html');
    if (fs.existsSync(indexPath)) {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(fs.readFileSync(indexPath));
      return;
    }
  }

  res.writeHead(404);
  res.end('Not Found');
});

// ── WebSocket Server (audio ingestion) ─────────────────────────────

const wss = new WebSocketServer({ noServer: true });
const dashboardWss = new WebSocketServer({ noServer: true });

httpServer.on('upgrade', (request, socket, head) => {
  const pathname = request.url;
  if (pathname === '/dashboard') {
    dashboardWss.handleUpgrade(request, socket, head, (ws) => {
      dashboardWss.emit('connection', ws, request);
    });
  } else if (pathname === '/' || pathname === '') {
    wss.handleUpgrade(request, socket, head, (ws) => {
      wss.emit('connection', ws, request);
    });
  } else {
    socket.destroy();
  }
});

// Track which session is associated with each WebSocket connection
const wsSessionMap = new Map<WebSocket, AudioSession>();
const dashboardClients = new Set<WebSocket>();

dashboardWss.on('connection', (ws) => {
  dashboardClients.add(ws);
  ws.on('close', () => dashboardClients.delete(ws));
});

function broadcastToDashboard(msg: any) {
  const payload = JSON.stringify(msg);
  for (const client of dashboardClients) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(payload);
    }
  }
}

wss.on('connection', (ws, req) => {
  const remoteAddr = req.socket.remoteAddress ?? 'unknown';
  logger.info('WEBSOCKET_CONNECTED', { remote: remoteAddr });

  ws.on('message', (data, isBinary) => {
    if (isBinary) {
      // Binary frame = PCM audio data
      handleBinaryMessage(ws, data as Buffer);
    } else {
      // Text frame = JSON protocol message
      handleTextMessage(ws, data.toString());
    }
  });

  ws.on('close', (code, reason) => {
    logger.info('WEBSOCKET_DISCONNECTED', { remote: remoteAddr, code, reason: reason.toString() });
    handleDisconnect(ws);
  });

  ws.on('error', (err) => {
    logger.error('WEBSOCKET_ERROR', { remote: remoteAddr, error: err.message });
    handleDisconnect(ws);
  });
});

// ── Message handlers ───────────────────────────────────────────────

function handleTextMessage(ws: WebSocket, raw: string): void {
  let msg;
  try {
    msg = parseMessage(raw);
  } catch (err) {
    if (err instanceof ProtocolError) {
      logger.warn('PROTOCOL_ERROR', { code: err.code, message: err.message });
      ws.send(JSON.stringify({ type: 'error', code: err.code, message: err.message }));
    } else {
      logger.error('PARSE_ERROR', { error: String(err) });
    }
    return;
  }

  switch (msg.type) {
    case 'session.start': {
      // Check if this WS already has a session
      if (wsSessionMap.has(ws)) {
        const existing = wsSessionMap.get(ws)!;
        logger.warn('DUPLICATE_SESSION_START', { existing: existing.sessionId, new: msg.session_id });
        ws.send(JSON.stringify({
          type: 'error',
          code: 'DUPLICATE_START',
          message: `WebSocket already has session: ${existing.sessionId}`,
        }));
        return;
      }

      try {
        const session = sessionManager.createSession(msg);
        wsSessionMap.set(ws, session);

        // Start debug recording if enabled
        if (debugRecorder) {
          debugRecorder.start(
            session.sessionId,
            session.format.sampleRate,
            session.format.channels,
            session.format.encoding,
          );
        }

        ws.send(JSON.stringify({
          type: 'session.started',
          session_id: session.sessionId,
          chunk_bytes: session.chunker.chunkBytes,
          chunk_duration_ms: session.chunker.chunkDurationMs,
        }));
      } catch (err) {
        logger.error('SESSION_CREATE_ERROR', { error: String(err) });
        ws.send(JSON.stringify({ type: 'error', code: 'SESSION_ERROR', message: String(err) }));
      }
      break;
    }

    case 'session.stop': {
      const session = wsSessionMap.get(ws);
      if (!session) {
        logger.warn('SESSION_NOT_FOUND', { session_id: msg.session_id, event: 'stop' });
        return;
      }

      if (session.sessionId !== msg.session_id) {
        logger.warn('SESSION_ID_MISMATCH', {
          expected: session.sessionId,
          received: msg.session_id,
        });
        return;
      }

      const partial = session.stop();

      // Send partial chunk to ML if it exists
      if (partial) {
        mlClient.sendChunk(session.sessionId, partial, session.format);
      }

      // Stop debug recording
      if (debugRecorder) {
        debugRecorder.stop(session.sessionId);
      }

      sessionManager.removeSession(session.sessionId);
      wsSessionMap.delete(ws);

      ws.send(JSON.stringify({
        type: 'session.stopped',
        session_id: session.sessionId,
        total_chunks: session.chunker.currentSequence,
        total_bytes: session.totalBytesReceived,
        invariant_ok: session.chunker.checkInvariant(),
      }));
      break;
    }
  }
}

function computeRMS(buffer: Buffer): number {
  if (buffer.length === 0) return 0;
  let sum = 0;
  for (let i = 0; i < buffer.length; i += 2) {
    const val = buffer.readInt16LE(i);
    sum += val * val;
  }
  return Math.sqrt(sum / (buffer.length / 2));
}

function handleBinaryMessage(ws: WebSocket, data: Buffer): void {
  const session = wsSessionMap.get(ws);
  if (!session) {
    logger.warn('AUDIO_NO_SESSION', { bytes: data.length });
    return;
  }

  // Write to debug recorder
  if (debugRecorder) {
    debugRecorder.write(session.sessionId, data);
  }

  const rms = computeRMS(data);
  broadcastToDashboard({
    type: 'stats',
    session_id: session.sessionId,
    rms,
    status: session.status,
    bytes: session.totalBytesReceived
  });

  // Push through the chunker
  const chunks = session.pushAudio(data);

  // Forward complete chunks to ML
  for (const chunk of chunks) {
    mlClient.sendChunk(session.sessionId, chunk, session.format);
  }
}

function handleDisconnect(ws: WebSocket): void {
  const session = wsSessionMap.get(ws);
  if (session) {
    logger.warn('SESSION_DISCONNECT', { session: session.sessionId, status: session.status });

    if (session.status === 'STREAMING') {
      const partial = session.stop();
      if (partial) {
        mlClient.sendChunk(session.sessionId, partial, session.format);
      }
    }

    if (debugRecorder) {
      debugRecorder.stop(session.sessionId);
    }

    sessionManager.removeSession(session.sessionId);
    wsSessionMap.delete(ws);
  }
}

// ── Startup ────────────────────────────────────────────────────────

// Connect to ML service (non-blocking — gateway works without ML)
mlClient.connect();

httpServer.listen(config.port, config.host, () => {
  logger.info('GATEWAY_STARTED', {
    port: config.port,
    host: config.host,
    mlUrl: config.mlWsUrl,
    chunkDuration: `${config.chunkDurationSec}s`,
    debugAudio: config.saveDebugAudio,
  });
});

// ── Graceful shutdown ──────────────────────────────────────────────

function shutdown(): void {
  logger.info('GATEWAY_SHUTTING_DOWN');
  sessionManager.stopAll();
  mlClient.disconnect();
  debugRecorder?.stopAll();
  wss.close();
  httpServer.close();
  process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

// Export for testing
export { httpServer, wss, dashboardWss, sessionManager, mlClient };
