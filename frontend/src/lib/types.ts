export type GatewayStatus = 'ONLINE' | 'OFFLINE';

export interface SystemStats {
  totalCalls: number;
  totalChunks: number;
  totalAudioBytes: number;
  recordings: number;
  totalStorageBytes: number;
}

export interface NetworkInfo {
  recommendedIp: string;
  interfaces: string[];
  port: number;
}

export interface LiveSession {
  sessionId: string;
  status: 'STREAMING' | 'COMPLETED';
  rms: number;
  bytes: number;
  bufferedBytes: number;
  chunkBytes: number;
  chunksEmitted: number;
}

export interface Chunk {
  sequence: number;
  bytes: number;
  durationMs: number;
  timestampMs: number;
  mlStatus: 'PENDING' | 'SENT' | 'OK' | 'DETECTOR_UNAVAILABLE' | 'DECODE_ERROR' | string;
  deepfakeScore?: number;
  latencyMs?: number;
  anomalyScore?: number;
  speakerMatch?: string;
}

export interface ConnectionEvent {
  id: string;
  call_id: string;
  session_id: string;
  event_type: string;
  created_at: string;
}

export interface Call {
  id: string;
  session_id: string;
  source: string;
  status: string;
  created_at: string;
  ended_at: string | null;
  duration_ms: number;
  ai_likelihood_pct?: number | null;
  audio_streams?: {
    sample_rate: number;
    channels: number;
    encoding: string;
    bytes_received: number;
  }[];
  recordings?: {
    id: string;
    format: string;
    size_bytes: number;
    duration_ms: number;
  }[];
}
