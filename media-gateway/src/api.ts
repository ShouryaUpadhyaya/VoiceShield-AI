import express from 'express';
import { prisma, auditOutbox } from './persistence.js';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { logger } from './logger.js';
import { summarizeRisk } from './risk-summary.js';
import { pcm16ToWav } from './live-chunk-audio.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const apiRouter = express.Router();

apiRouter.get('/stats', async (req, res) => {
  try {
    const totalCalls = await prisma.calls.count();
    const totalChunks = await prisma.audio_chunks.count();
    const streams = await prisma.audio_streams.aggregate({ _sum: { bytes_received: true } });
    const recordings = await prisma.recordings.count();
    const recordingBytes = await prisma.recordings.aggregate({ _sum: { size_bytes: true } });

    res.json({
      totalCalls,
      totalChunks,
      totalAudioBytes: streams._sum.bytes_received || 0,
      recordings,
      totalStorageBytes: recordingBytes._sum.size_bytes || 0,
    });
  } catch (err) {
    logger.error('API_ERROR', { url: req.originalUrl, error: String(err) });
    res.json({
      totalCalls: 0,
      totalChunks: 0,
      totalAudioBytes: 0,
      recordings: 0,
      totalStorageBytes: 0
    });
  }
});

apiRouter.get('/calls', async (req, res) => {
  try {
    const calls = await prisma.calls.findMany({
      orderBy: { created_at: 'desc' },
      take: 50,
      include: {
        audio_streams: true,
        recordings: true
      }
    });
    res.json(calls);
  } catch (err) {
    logger.error('API_ERROR', { url: req.originalUrl, error: String(err) });
    res.json([]);
  }
});

apiRouter.get('/calls/:id', async (req, res) => {
  try {
    const callId = req.params.id;
    const call = await prisma.calls.findUnique({
      where: { id: callId },
      include: {
        audio_streams: true,
        audio_chunks: { 
          orderBy: { sequence_number: 'asc' },
          include: { ml_results: true }
        },
        recordings: true,
        connection_events: { orderBy: { timestamp: 'asc' } }
      }
    });
    if (call) {
      res.json({ ...call, risk_summary: summarizeRisk(call.audio_chunks.flatMap(c => c.ml_results.map(r => r.result_json)), call.audio_chunks.length) });
    } else {
      res.status(404).json({ error: 'Call not found' });
    }
  } catch (err) {
    logger.error('API_ERROR', { url: req.originalUrl, error: String(err) });
    res.status(500).json({ error: 'Internal server error', details: String(err) });
  }
});

apiRouter.get('/calls/:id/recording', async (req, res) => {
  try {
    const callId = req.params.id;
    const rec = await prisma.recordings.findFirst({ where: { call_id: callId } });
    if (rec) {
      // Safe path resolution
      const safeBase = path.resolve(path.join(__dirname, '..', 'data', 'calls'));
      const resolved = path.resolve(rec.storage_path);
      if (resolved.startsWith(safeBase) && fs.existsSync(resolved)) {
        res.setHeader('Content-Type', 'audio/wav');
        res.setHeader('Content-Disposition', `attachment; filename="call-${callId}.wav"`);
        fs.createReadStream(resolved).pipe(res);
        return;
      }
    }
    res.status(404).json({ error: 'Recording not found' });
  } catch (err) {
    logger.error('API_ERROR', { url: req.originalUrl, error: String(err) });
    res.status(500).json({ error: 'Internal server error', details: String(err) });
  }
});

apiRouter.get('/live-sessions/:sessionId/chunks/:sequence/audio', async (req, res) => {
  try {
    const sequence = Number.parseInt(req.params.sequence, 10);
    if (!Number.isInteger(sequence) || sequence < 0) return res.status(400).json({ error: 'Invalid chunk sequence' });
    const call = await prisma.calls.findFirst({
      where: { session_id: req.params.sessionId, status: 'IN_PROGRESS' },
      include: { audio_streams: { take: 1 }, audio_chunks: { orderBy: { sequence_number: 'asc' } } },
    });
    const target = call?.audio_chunks.find(chunk => chunk.sequence_number === sequence);
    const stream = call?.audio_streams[0];
    if (!call || !target || !stream) return res.status(404).json({ error: 'Live chunk not available' });

    const safeSessionId = path.basename(call.session_id);
    if (safeSessionId !== call.session_id) return res.status(400).json({ error: 'Invalid session identifier' });
    const tempPath = path.resolve(path.join(__dirname, '..', 'data', 'calls', `${safeSessionId}.pcm.tmp`));
    const safeBase = path.resolve(path.join(__dirname, '..', 'data', 'calls'));
    if (!tempPath.startsWith(safeBase) || !fs.existsSync(tempPath)) return res.status(404).json({ error: 'Live audio is no longer available' });

    const offset = call.audio_chunks.filter(chunk => chunk.sequence_number < sequence)
      .reduce((total, chunk) => total + chunk.byte_size, 0);
    const pcm = (await fsp.readFile(tempPath)).subarray(offset, offset + target.byte_size);
    if (pcm.length !== target.byte_size) return res.status(409).json({ error: 'Chunk audio has not fully persisted yet' });
    res.setHeader('Content-Type', 'audio/wav');
    res.send(pcm16ToWav(pcm, stream.sample_rate, stream.channels));
  } catch (err) {
    logger.error('LIVE_CHUNK_AUDIO_ERROR', { url: req.originalUrl, error: String(err) });
    res.status(500).json({ error: 'Unable to prepare live chunk audio' });
  }
});

apiRouter.get('/calls/:id/audit', async (req, res) => {
  try {
    res.json((await auditOutbox.getByCall(req.params.id)) ?? { state: 'NOT_ANCHORED' });
  } catch (err) {
    logger.error('AUDIT_API_ERROR', { url: req.originalUrl, error: String(err) });
    res.status(500).json({ error: 'Unable to retrieve audit record' });
  }
});

apiRouter.get('/calls/:id/verify', async (req, res) => {
  try {
    res.json(await auditOutbox.verifyCall(req.params.id));
  } catch (err) {
    logger.error('AUDIT_VERIFY_ERROR', { url: req.originalUrl, error: String(err) });
    res.status(500).json({ verified: false, status: 'FAILED', error: 'Integrity verification failed to run' });
  }
});

apiRouter.post('/calls/:id/audit/retry', async (req, res) => {
  const audit = await auditOutbox.getByCall(req.params.id);
  if (!audit) return res.status(404).json({ error: 'Audit record not found' });
  await auditOutbox.run(audit.id);
  res.json(await auditOutbox.getByCall(req.params.id));
});

apiRouter.get('/logs', async (req, res) => {
  try {
    const logs = await prisma.connection_events.findMany({
      orderBy: { timestamp: 'desc' },
      take: 100
    });
    res.json(logs);
  } catch (err) {
    logger.error('API_ERROR', { url: req.originalUrl, error: String(err) });
    res.json([]);
  }
});

apiRouter.get('/tests', async (req, res) => {
  try {
    const tests = await prisma.model_test_runs.findMany({
      orderBy: { created_at: 'desc' },
      take: 100
    });
    res.json(tests);
  } catch (err) {
    logger.error('API_ERROR', { url: req.originalUrl, error: String(err) });
    res.status(500).json({ error: 'Internal server error', details: String(err) });
  }
});

apiRouter.post('/tests', express.json(), async (req, res) => {
  try {
    const { filename, duration, model, model_version, status, latency_ms, result_json, fusion_config_json, final_score, is_pipeline } = req.body;
    const testRun = await prisma.model_test_runs.create({
      data: {
        filename,
        duration,
        model,
        model_version,
        status,
        latency_ms,
        result_json,
        fusion_config_json,
        final_score,
        is_pipeline: is_pipeline || false
      }
    });
    res.json(testRun);
  } catch (err) {
    logger.error('API_ERROR', { url: req.originalUrl, error: String(err) });
    res.status(500).json({ error: 'Internal server error', details: String(err) });
  }
});
