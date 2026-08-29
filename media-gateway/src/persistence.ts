import { PrismaClient } from '@prisma/client';
import { Pool } from 'pg';
import { PrismaPg } from '@prisma/adapter-pg';
import { logger } from './logger.js';
import type { AudioSession } from './session.js';
import type { RecordingInfo } from './call-recorder.js';
import type { ChunkOutput } from './chunker.js';

const connectionString = process.env.DATABASE_URL;
const pool = new Pool({ connectionString });
const adapter = new PrismaPg(pool);

export const prisma = new PrismaClient({ adapter });

// In-memory queue to ensure DB operations don't block audio loop
const eventQueue: (() => Promise<void>)[] = [];
let isProcessing = false;

export function queueDbOperation(op: () => Promise<void>) {
  eventQueue.push(op);
  processQueue();
}

async function processQueue() {
  if (isProcessing) return;
  isProcessing = true;
  
  while (eventQueue.length > 0) {
    const op = eventQueue.shift();
    if (op) {
      try {
        await op();
      } catch (err) {
        logger.error('DATABASE_ERROR', { error: String(err) });
        import('node:fs').then(fs => fs.appendFileSync('db_error.log', String(err) + '\n'));
      }
    }
  }
  
  isProcessing = false;
}

// Higher level persistence functions

export function persistSessionStart(session: AudioSession, callId: string) {
  queueDbOperation(async () => {
    await prisma.calls.create({
      data: {
        id: callId,
        session_id: session.sessionId,
        source: session.source,
        status: 'IN_PROGRESS'
      }
    });

    await prisma.audio_streams.create({
      data: {
        call_id: callId,
        sample_rate: session.format.sampleRate,
        channels: session.format.channels,
        encoding: session.format.encoding,
        bytes_received: 0,
        duration_ms: 0
      }
    });

    await prisma.connection_events.create({
      data: {
        call_id: callId,
        session_id: session.sessionId,
        event_type: 'SESSION_START'
      }
    });
  });
}

export function persistChunk(callId: string, chunk: ChunkOutput) {
  queueDbOperation(async () => {
    await prisma.audio_chunks.create({
      data: {
        call_id: callId,
        sequence_number: chunk.sequence,
        timestamp_ms: chunk.timestampMs,
        duration_ms: chunk.durationMs,
        byte_size: chunk.data.length,
        status: 'PROCESSED'
      }
    });
  });
}

export function persistSessionStop(session: AudioSession, callId: string, recordingInfo: RecordingInfo | null) {
  queueDbOperation(async () => {
    // End the call
    await prisma.calls.update({
      where: { id: callId },
      data: {
        status: 'COMPLETED',
        ended_at: new Date(),
        duration_ms: recordingInfo ? recordingInfo.durationMs : 0
      }
    });

    // Update audio stream final bytes
    const streams = await prisma.audio_streams.findFirst({ where: { call_id: callId } });
    if (streams) {
      await prisma.audio_streams.update({
        where: { id: streams.id },
        data: {
          bytes_received: session.totalBytesReceived,
          duration_ms: recordingInfo ? recordingInfo.durationMs : 0
        }
      });
    }

    // Insert recording metadata
    if (recordingInfo) {
      await prisma.recordings.create({
        data: {
          call_id: callId,
          storage_path: recordingInfo.path,
          format: recordingInfo.format,
          size_bytes: recordingInfo.sizeBytes,
          duration_ms: recordingInfo.durationMs
        }
      });
    }

    await prisma.connection_events.create({
      data: {
        call_id: callId,
        session_id: session.sessionId,
        event_type: 'SESSION_STOP'
      }
    });
  });
}
