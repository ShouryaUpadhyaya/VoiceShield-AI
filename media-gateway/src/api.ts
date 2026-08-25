import type { IncomingMessage, ServerResponse } from 'node:http';
import { prisma } from './persistence.js';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { logger } from './logger.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export async function handleApiRequest(req: IncomingMessage, res: ServerResponse): Promise<boolean> {
  const url = req.url || '';
  if (!url.startsWith('/api/')) return false;

  try {
    if (req.method === 'GET') {
      if (url === '/api/stats') {
        const totalCalls = await prisma.calls.count();
        const totalChunks = await prisma.audio_chunks.count();
        const streams = await prisma.audio_streams.aggregate({ _sum: { bytes_received: true } });
        const recordings = await prisma.recordings.count();
        const recordingBytes = await prisma.recordings.aggregate({ _sum: { size_bytes: true } });

        res.setHeader('Content-Type', 'application/json');
        res.writeHead(200);
        res.end(JSON.stringify({
          totalCalls,
          totalChunks,
          totalAudioBytes: streams._sum.bytes_received || 0,
          recordings,
          totalStorageBytes: recordingBytes._sum.size_bytes || 0,
        }));
        return true;
      }

      if (url === '/api/calls') {
        const calls = await prisma.calls.findMany({
          orderBy: { created_at: 'desc' },
          take: 50,
          include: {
            audio_streams: true,
            recordings: true
          }
        });
        res.setHeader('Content-Type', 'application/json');
        res.writeHead(200);
        res.end(JSON.stringify(calls));
        return true;
      }

      const callMatch = url.match(/^\/api\/calls\/([a-zA-Z0-9-]+)$/);
      if (callMatch) {
        const callId = callMatch[1];
        const call = await prisma.calls.findUnique({
          where: { id: callId },
          include: {
            audio_streams: true,
            audio_chunks: { orderBy: { sequence_number: 'asc' } },
            recordings: true,
            connection_events: { orderBy: { timestamp: 'asc' } }
          }
        });
        res.setHeader('Content-Type', 'application/json');
        if (call) {
          res.writeHead(200);
          res.end(JSON.stringify(call));
        } else {
          res.writeHead(404);
          res.end(JSON.stringify({ error: 'Call not found' }));
        }
        return true;
      }

      const recMatch = url.match(/^\/api\/calls\/([a-zA-Z0-9-]+)\/recording$/);
      if (recMatch) {
        const callId = recMatch[1];
        const rec = await prisma.recordings.findFirst({ where: { call_id: callId } });
        if (rec) {
          // Safe path resolution
          const safeBase = path.resolve(path.join(__dirname, '..', 'data', 'calls'));
          const resolved = path.resolve(rec.storage_path);
          if (resolved.startsWith(safeBase) && fs.existsSync(resolved)) {
            res.setHeader('Content-Type', 'audio/wav');
            res.setHeader('Content-Disposition', `attachment; filename="call-${callId}.wav"`);
            res.writeHead(200);
            fs.createReadStream(resolved).pipe(res);
            return true;
          }
        }
        res.setHeader('Content-Type', 'application/json');
        res.writeHead(404);
        res.end(JSON.stringify({ error: 'Recording not found' }));
        return true;
      }

      if (url === '/api/logs') {
        const logs = await prisma.connection_events.findMany({
          orderBy: { timestamp: 'desc' },
          take: 100
        });
        res.setHeader('Content-Type', 'application/json');
        res.writeHead(200);
        res.end(JSON.stringify(logs));
        return true;
      }
    }
  } catch (err) {
    logger.error('API_ERROR', { url, error: String(err) });
    res.setHeader('Content-Type', 'application/json');
    res.writeHead(500);
    res.end(JSON.stringify({ error: 'Internal server error', details: String(err) }));
    return true;
  }

  res.setHeader('Content-Type', 'application/json');
  res.writeHead(404);
  res.end(JSON.stringify({ error: 'Not found' }));
  return true;
}
