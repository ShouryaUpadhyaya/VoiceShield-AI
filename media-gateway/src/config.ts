/**
 * Media Gateway Configuration
 *
 * All configuration is loaded from environment variables with sensible defaults.
 * Chunk size is CALCULATED from audio format parameters, never hardcoded.
 */

import 'dotenv/config';

export interface GatewayConfig {
  /** WebSocket server port */
  port: number;
  /** WebSocket server host */
  host: string;
  /** ML service WebSocket URL */
  mlWsUrl: string;
  /** Audio chunk duration in seconds */
  chunkDurationSec: number;
  /** Whether to save debug audio recordings */
  saveDebugAudio: boolean;
  /** Directory for debug audio recordings */
  debugAudioDir: string;
  /** Log level */
  logLevel: 'debug' | 'info' | 'warn' | 'error';
}

export function loadConfig(): GatewayConfig {
  return {
    port: parseInt(process.env.PORT ?? '8010', 10),
    host: process.env.HOST ?? '0.0.0.0',
    mlWsUrl: process.env.ML_WS_URL ?? 'ws://localhost:8011',
    chunkDurationSec: parseInt(process.env.CHUNK_DURATION_SEC ?? '3', 10),
    saveDebugAudio: process.env.SAVE_DEBUG_AUDIO === 'true',
    debugAudioDir: process.env.DEBUG_AUDIO_DIR ?? './debug-recordings',
    logLevel: (process.env.LOG_LEVEL as GatewayConfig['logLevel']) ?? 'info',
  };
}

/**
 * Calculate the exact byte size of one audio chunk given the format and duration.
 *
 * This is THE canonical chunk-size calculation — no magic 96000 scattered anywhere.
 */
export function calculateChunkBytes(
  sampleRate: number,
  channels: number,
  bytesPerSample: number,
  durationSec: number,
): number {
  return sampleRate * channels * bytesPerSample * durationSec;
}

/**
 * Bytes-per-sample for known encodings.
 */
export function bytesPerSampleForEncoding(encoding: string): number {
  switch (encoding) {
    case 'pcm_s16le':
    case 'pcm_s16be':
      return 2;
    case 'pcm_f32le':
      return 4;
    default:
      throw new Error(`Unsupported encoding: ${encoding}`);
  }
}
