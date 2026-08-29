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
import { Server, Socket as IoSocket } from 'socket.io';
import { WebSocketServer, WebSocket } from 'ws';
import { loadConfig, type GatewayConfig } from './config.js';
import { parseMessage, ProtocolError } from './protocol.js';
import { SessionManager, type AudioSession } from './session.js';
import { MlClient } from './ml-client.js';
import { DebugRecorder } from './debug-recorder.js';
import { CallRecorder } from './call-recorder.js';
import { persistSessionStart, persistChunk, persistSessionStop } from './persistence.js';
import { getLocalIpAddresses, getRecommendedLanIp } from './network.js';
import { logger, setLogLevel } from './logger.js';
import express from 'express';
import cors from 'cors';
import { apiRouter } from './api.js';
import { randomUUID } from 'node:crypto';
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
const callRecorder = new CallRecorder(path.join(__dirname, '..', 'data', 'calls'));
const callIdMap = new Map<string, string>();

// ── HTTP Server (health endpoint) ──────────────────────────────────

const app = express();
app.use(cors());
app.use(express.json());

// API Routes
app.use('/api', apiRouter);

// Health endpoint
app.get('/health', (req, res) => {
  const health = {
    status: 'ok',
    mlConnected: mlClient.isConnected,
    activeSessions: sessionManager.activeCount,
    sessions: sessionManager.getSessionInfos(),
    uptime: process.uptime(),
    network: {
      recommendedIp: getRecommendedLanIp(),
      interfaces: getLocalIpAddresses(),
      port: config.port,
    }
  };
  res.json(health);
});

// Serve static files (Dashboard)
app.use(express.static(path.join(__dirname, '..', 'public')));

// Create HTTP server from Express app
const httpServer = http.createServer(app);

// ── Socket.IO Server (audio ingestion) ─────────────────────────────

const io = new Server(httpServer, {
  cors: { origin: '*' },
  maxHttpBufferSize: 1e7 // 10 MB for large audio chunks if needed
});

const dashboardIo = io.of('/dashboard');

const wss = new WebSocketServer({ noServer: true });

httpServer.on('upgrade', (request, socket, head) => {
  const pathname = request.url;
  // Let Socket.IO handle its own paths natively.
  // We explicitly catch root paths for raw websocket audio ingestion.
  if (pathname === '/' || pathname === '') {
    wss.handleUpgrade(request, socket, head, (ws) => {
      wss.emit('connection', ws, request);
    });
  }
});

// Track which session is associated with each Socket
const socketSessionMap = new Map<WebSocket, AudioSession>();

dashboardIo.on('connection', (socket) => {
  // Send initial gateway state
  socket.emit('gateway_state', {
    status: 'ONLINE',
    network: {
      recommendedIp: getRecommendedLanIp(),
      interfaces: getLocalIpAddresses(),
      port: config.port,
    }
  });
});

function broadcastToDashboard(msg: any) {
  // Emit the message using its type as the event name for cleaner client logic
  dashboardIo.emit(msg.type, msg);
}

wss.on('connection', (ws, req) => {
  const remoteAddr = req.socket.remoteAddress ?? 'unknown';
  logger.info('SOCKET_CONNECTED', { remote: remoteAddr });

  ws.on('message', (data: Buffer, isBinary: boolean) => {
    if (isBinary) {
      // Binary frame -> audio data
      handleBinaryMessage(ws, data);
    } else {
      // Text frame -> control message
      handleTextMessage(ws, data.toString('utf8'));
    }
  });

  ws.on('close', (code, reason) => {
    logger.info('SOCKET_DISCONNECTED', { remote: remoteAddr, code, reason: reason.toString() });
    handleDisconnect(ws);
  });

  ws.on('error', (err) => {
    logger.error('SOCKET_ERROR', { remote: remoteAddr, error: err.message });
    handleDisconnect(ws);
  });
});

// ── Message handlers ───────────────────────────────────────────────

function handleTextMessage(ws: WebSocket, rawMsg: string | Buffer): void {
  let msg;
  try {
    msg = parseMessage(rawMsg);
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
      // Check if this Socket already has a session
      if (socketSessionMap.has(ws)) {
        const existing = socketSessionMap.get(ws)!;
        logger.warn('DUPLICATE_SESSION_START', { existing: existing.sessionId, new: msg.session_id });
        ws.send(JSON.stringify({
          type: 'error',
          code: 'DUPLICATE_START',
          message: `Socket already has session: ${existing.sessionId}`,
        }));
        return;
      }

      try {
        const session = sessionManager.createSession(msg);
        socketSessionMap.set(ws, session);
        
        const callId = randomUUID();
        callIdMap.set(session.sessionId, callId);
        
        callRecorder.start(
          session.sessionId,
          session.format.sampleRate,
          session.format.channels,
          session.format.encoding,
        );
        persistSessionStart(session, callId);

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
      const session = socketSessionMap.get(ws);
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
        const callId = callIdMap.get(session.sessionId);
        if (callId) persistChunk(callId, partial);
      }

      // Stop debug recording
      if (debugRecorder) {
        debugRecorder.stop(session.sessionId);
      }
      
      callRecorder.stop(session.sessionId).then((recordingInfo) => {
        const callId = callIdMap.get(session.sessionId);
        if (callId) {
          persistSessionStop(session, callId, recordingInfo);
          callIdMap.delete(session.sessionId);
        }
      });

      sessionManager.removeSession(session.sessionId);
      socketSessionMap.delete(ws);

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
  const session = socketSessionMap.get(ws);
  if (!session) {
    logger.warn('AUDIO_NO_SESSION', { bytes: data.length });
    return;
  }

  // Write to debug recorder
  if (debugRecorder) {
    debugRecorder.write(session.sessionId, data);
  }
  callRecorder.write(session.sessionId, data);

  const rms = computeRMS(data);
  broadcastToDashboard({
    type: 'stats',
    session_id: session.sessionId,
    rms,
    status: session.status,
    bytes: session.totalBytesReceived,
    buffered_bytes: session.chunker.bufferedBytes,
    chunk_bytes: session.chunker.chunkBytes,
    chunks_emitted: session.chunker.currentSequence,
  });

  // Push through the chunker
  const chunks = session.pushAudio(data);

  // Forward complete chunks to ML and Dashboard
  for (const chunk of chunks) {
    mlClient.sendChunk(session.sessionId, chunk, session.format);
    
    const callId = callIdMap.get(session.sessionId);
    if (callId) persistChunk(callId, chunk);
    
    broadcastToDashboard({
      type: 'chunk_created',
      session_id: session.sessionId,
      sequence: chunk.sequence,
      bytes: chunk.data.length,
      durationMs: chunk.durationMs,
      timestampMs: chunk.timestampMs,
    });
  }
}

function handleDisconnect(ws: WebSocket): void {
  const session = socketSessionMap.get(ws);
  if (session) {
    logger.warn('SESSION_DISCONNECT', { session: session.sessionId, status: session.status });

    if (session.status === 'STREAMING') {
      const partial = session.stop();
      if (partial) {
        mlClient.sendChunk(session.sessionId, partial, session.format);
        const callId = callIdMap.get(session.sessionId);
        if (callId) persistChunk(callId, partial);
      }
    }

    if (debugRecorder) {
      debugRecorder.stop(session.sessionId);
    }
    
    callRecorder.stop(session.sessionId).then((recordingInfo) => {
      const callId = callIdMap.get(session.sessionId);
      if (callId) {
        persistSessionStop(session, callId, recordingInfo);
        callIdMap.delete(session.sessionId);
      }
    });

    sessionManager.removeSession(session.sessionId);
    socketSessionMap.delete(ws);
  }
}

// ── Startup ────────────────────────────────────────────────────────

// Connect to ML service (non-blocking — gateway works without ML)
if (process.env.NODE_ENV !== 'test') {
  mlClient.connect();
  mlClient.on('score', (msg) => {
    if (msg.metadata?.session_id) {
      dashboardIo.emit('ml_result', {
        session_id: msg.metadata.session_id,
        window_seq: msg.window_seq,
        status: msg.status,
        signals: msg.signals,
      });
    }
  });

  httpServer.on('error', (err: any) => {
    if (err.code === 'EADDRINUSE') {
      logger.error('STARTUP_ERROR', { 
        message: `Media Gateway could not start. Port ${config.port} is already in use. Check: lsof -i :${config.port}. If the existing VoiceShield gateway is already running, use it instead of starting another instance.`
      });
      process.exit(1);
    } else {
      logger.error('SERVER_ERROR', { error: err.message });
      process.exit(1);
    }
  });

  httpServer.listen(config.port, config.host, () => {
    logger.info('GATEWAY_STARTED', {
      port: config.port,
      host: config.host,
      mlUrl: config.mlWsUrl,
      chunkDuration: `${config.chunkDurationSec}s`,
      debugAudio: config.saveDebugAudio,
    });
  });
}

// ── Graceful shutdown ──────────────────────────────────────────────

function shutdown(): void {
  logger.info('GATEWAY_SHUTTING_DOWN');
  sessionManager.stopAll();
  mlClient.disconnect();
  debugRecorder?.stopAll();
  callRecorder.stopAll();
  io.close();
  wss.close();
  httpServer.close();
  process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

// Export for testing
export { httpServer, io, dashboardIo, wss, sessionManager, mlClient };
