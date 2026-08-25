/**
 * Synthetic Test Audio Sender
 *
 * Generates a 1kHz sine wave and sends it to the gateway over WebSocket.
 * Proves the gateway works independently of CallVault/FreeSWITCH.
 *
 * Usage:
 *   tsx scripts/send-test-audio.ts
 *   tsx scripts/send-test-audio.ts --duration 30 --rate 16000
 *   tsx scripts/send-test-audio.ts --url ws://localhost:8010 --duration 10
 */

import WebSocket from 'ws';
import { randomUUID } from 'node:crypto';

// ── Parse CLI args ─────────────────────────────────────────────────

function parseArgs() {
  const args = process.argv.slice(2);
  const opts: Record<string, string> = {};
  for (let i = 0; i < args.length; i += 2) {
    if (args[i].startsWith('--') && args[i + 1]) {
      opts[args[i].slice(2)] = args[i + 1];
    }
  }
  return {
    url: opts.url ?? 'ws://localhost:8010',
    duration: parseInt(opts.duration ?? '10', 10),
    rate: parseInt(opts.rate ?? '16000', 10),
    source: opts.source ?? 'test-synthetic',
  };
}

const config = parseArgs();
const FREQ = 1000; // 1 kHz sine wave
const CHANNELS = 1;
const BPS = 2; // PCM 16-bit
const FRAME_SIZE = 4096; // bytes per WebSocket frame
const FRAME_DELAY_MS = 25; // delay between frames

// ── Generate PCM ───────────────────────────────────────────────────

function generateSineWave(sampleRate: number, durationSec: number, freq: number): Buffer {
  const totalSamples = sampleRate * durationSec;
  const buf = Buffer.alloc(totalSamples * BPS);

  for (let i = 0; i < totalSamples; i++) {
    const t = i / sampleRate;
    const sample = Math.sin(2 * Math.PI * freq * t);
    const int16 = Math.round(sample * 32767);
    buf.writeInt16LE(int16, i * BPS);
  }
  return buf;
}

// ── Helpers ────────────────────────────────────────────────────────

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ── Main ───────────────────────────────────────────────────────────

async function main() {
  const sessionId = randomUUID();
  const totalBytes = config.rate * CHANNELS * BPS * config.duration;
  const chunkBytes = config.rate * CHANNELS * BPS * 3;
  const completeChunks = Math.floor(totalBytes / chunkBytes);
  const remainder = totalBytes % chunkBytes;
  const expectedTotalChunks = completeChunks + (remainder > 0 ? 1 : 0); // includes partial flush

  console.log('=== Synthetic Audio Sender ===');
  console.log(`URL:       ${config.url}`);
  console.log(`Session:   ${sessionId}`);
  console.log(`Duration:  ${config.duration}s`);
  console.log(`Rate:      ${config.rate} Hz`);
  console.log(`Source:    ${config.source}`);
  console.log(`Frequency: ${FREQ} Hz sine wave`);
  console.log(`Total:     ${totalBytes.toLocaleString()} bytes`);
  console.log(`Expected:  ${completeChunks} complete chunks + ${remainder > 0 ? `1 partial (${remainder.toLocaleString()} bytes)` : 'no remainder'} = ${expectedTotalChunks} total`);
  console.log('');

  // Generate audio
  console.log('Generating PCM audio...');
  const pcm = generateSineWave(config.rate, config.duration, FREQ);
  console.log(`Generated ${pcm.length.toLocaleString()} bytes`);

  // Connect
  console.log(`Connecting to ${config.url}...`);
  const ws = new WebSocket(config.url);

  await new Promise<void>((resolve, reject) => {
    ws.on('open', resolve);
    ws.on('error', reject);
  });
  console.log('Connected!\n');

  // Session start
  const startMsg = {
    type: 'session.start',
    session_id: sessionId,
    source: config.source,
    sample_rate: config.rate,
    channels: CHANNELS,
    encoding: 'pcm_s16le',
  };
  ws.send(JSON.stringify(startMsg));
  console.log('→ session.start sent');

  // Wait for ack
  await new Promise<void>((resolve) => {
    ws.once('message', (data) => {
      const resp = JSON.parse(data.toString());
      console.log(`← ${resp.type}: chunk_bytes=${resp.chunk_bytes} duration=${resp.chunk_duration_ms}ms`);
      resolve();
    });
  });

  // Send PCM frames
  let bytesSent = 0;
  let frameCount = 0;
  const startTime = Date.now();

  while (bytesSent < pcm.length) {
    const end = Math.min(bytesSent + FRAME_SIZE, pcm.length);
    const frame = pcm.subarray(bytesSent, end);
    ws.send(frame);
    bytesSent += frame.length;
    frameCount++;

    if (frameCount % 100 === 0) {
      const elapsed = (Date.now() - startTime) / 1000;
      const pct = ((bytesSent / pcm.length) * 100).toFixed(1);
      process.stdout.write(`\r  Sending... ${pct}% (${bytesSent.toLocaleString()} bytes, ${elapsed.toFixed(1)}s)`);
    }

    await sleep(FRAME_DELAY_MS);
  }

  const elapsed = (Date.now() - startTime) / 1000;
  console.log(`\n→ Sent ${bytesSent.toLocaleString()} bytes in ${frameCount} frames (${elapsed.toFixed(1)}s)\n`);

  // Session stop
  ws.send(JSON.stringify({ type: 'session.stop', session_id: sessionId }));
  console.log('→ session.stop sent');

  // Wait for stop ack
  await new Promise<void>((resolve) => {
    ws.once('message', (data) => {
      const resp = JSON.parse(data.toString());
      console.log(`← ${resp.type}:`);
      console.log(`   total_chunks: ${resp.total_chunks}`);
      console.log(`   total_bytes:  ${resp.total_bytes?.toLocaleString()}`);
      console.log(`   invariant_ok: ${resp.invariant_ok}`);
      console.log('');

      if (resp.total_chunks === expectedTotalChunks) {
        console.log(`✅ PASS: Got expected ${expectedTotalChunks} total chunks (${completeChunks} complete + ${remainder > 0 ? '1 partial' : '0 partial'})`);
      } else {
        console.log(`❌ FAIL: Expected ${expectedTotalChunks} total chunks, got ${resp.total_chunks}`);
      }
      resolve();
    });
  });

  ws.close();
  console.log('\nDone.');
  process.exit(0);
}

main().catch((err) => {
  console.error('FATAL:', err);
  process.exit(1);
});
