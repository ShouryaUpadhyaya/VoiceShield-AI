import "dotenv/config";

export interface GatewayConfig {
  port: number;
  host: string;
  mlWsUrl: string;
  chunkDurationSec: number;
  saveDebugAudio: boolean;
  debugAudioDir: string;
  logLevel: "debug" | "info" | "warn" | "error";
}

export function loadConfig(): GatewayConfig {
  return {
    port: parseInt(process.env.PORT ?? "8010", 10),
    host: process.env.HOST ?? "0.0.0.0",
    mlWsUrl: process.env.ML_WS_URL ?? "ws://localhost:8011",
    chunkDurationSec: parseInt(process.env.CHUNK_DURATION_SEC ?? "3", 10),
    saveDebugAudio: process.env.SAVE_DEBUG_AUDIO === "true",
    debugAudioDir: process.env.DEBUG_AUDIO_DIR ?? "./debug-recordings",
    logLevel: (process.env.LOG_LEVEL as GatewayConfig["logLevel"]) ?? "info",
  };
}

export function calculateChunkBytes(
  sampleRate: number,
  channels: number,
  bytesPerSample: number,
  durationSec: number,
): number {
  return sampleRate * channels * bytesPerSample * durationSec;
}

export function bytesPerSampleForEncoding(encoding: string): number {
  switch (encoding) {
    case "pcm_s16le":
    case "pcm_s16be":
      return 2;
    case "pcm_f32le":
      return 4;
    default:
      throw new Error(`Unsupported encoding: ${encoding}`);
  }
}
