/**
 * Source → Gateway Protocol Parser
 *
 * Validates and parses the protocol messages between audio sources
 * (CallVault, FreeSWITCH, synthetic) and this gateway.
 *
 * Protocol:
 *   1. JSON: session.start (with audio format metadata)
 *   2. Binary WebSocket frames: raw PCM audio
 *   3. JSON: session.stop
 */

/** Supported audio encodings */
const SUPPORTED_ENCODINGS = ['pcm_s16le'] as const;
export type SupportedEncoding = (typeof SUPPORTED_ENCODINGS)[number];

/** Supported sample rates */
const SUPPORTED_SAMPLE_RATES = [8000, 16000, 44100, 48000] as const;

/** Supported channel counts */
const SUPPORTED_CHANNELS = [1, 2] as const;

// ── Message types ──────────────────────────────────────────────────

export interface SessionStartMessage {
  type: 'session.start';
  session_id: string;
  source: string;
  sample_rate: number;
  channels: number;
  encoding: SupportedEncoding;
}

export interface SessionStopMessage {
  type: 'session.stop';
  session_id: string;
}

export type ProtocolMessage = SessionStartMessage | SessionStopMessage;

// ── Validation errors ──────────────────────────────────────────────

export class ProtocolError extends Error {
  constructor(
    message: string,
    public readonly code: string,
  ) {
    super(message);
    this.name = 'ProtocolError';
  }
}

// ── Parser ──────────────────────────────────────────────────────────

/**
 * Attempt to parse a text WebSocket message as a protocol message.
 * Throws ProtocolError for malformed or unsupported messages.
 */
export function parseMessage(raw: string): ProtocolMessage {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new ProtocolError('Invalid JSON', 'INVALID_JSON');
  }

  if (typeof parsed !== 'object' || parsed === null) {
    throw new ProtocolError('Message must be a JSON object', 'NOT_OBJECT');
  }

  const msg = parsed as Record<string, unknown>;

  if (typeof msg.type !== 'string') {
    throw new ProtocolError('Missing or invalid "type" field', 'MISSING_TYPE');
  }

  switch (msg.type) {
    case 'session.start':
      return parseSessionStart(msg);
    case 'session.stop':
      return parseSessionStop(msg);
    default:
      throw new ProtocolError(`Unknown message type: ${msg.type}`, 'UNKNOWN_TYPE');
  }
}

function parseSessionStart(msg: Record<string, unknown>): SessionStartMessage {
  // session_id
  if (typeof msg.session_id !== 'string' || msg.session_id.length === 0) {
    throw new ProtocolError('Missing or empty "session_id"', 'MISSING_SESSION_ID');
  }

  // source
  if (typeof msg.source !== 'string' || msg.source.length === 0) {
    throw new ProtocolError('Missing or empty "source"', 'MISSING_SOURCE');
  }

  // sample_rate
  if (typeof msg.sample_rate !== 'number') {
    throw new ProtocolError('Missing or invalid "sample_rate"', 'MISSING_SAMPLE_RATE');
  }
  if (!(SUPPORTED_SAMPLE_RATES as readonly number[]).includes(msg.sample_rate)) {
    throw new ProtocolError(
      `Unsupported sample_rate: ${msg.sample_rate}. Supported: ${SUPPORTED_SAMPLE_RATES.join(', ')}`,
      'UNSUPPORTED_SAMPLE_RATE',
    );
  }

  // channels
  if (typeof msg.channels !== 'number') {
    throw new ProtocolError('Missing or invalid "channels"', 'MISSING_CHANNELS');
  }
  if (!(SUPPORTED_CHANNELS as readonly number[]).includes(msg.channels)) {
    throw new ProtocolError(
      `Unsupported channels: ${msg.channels}. Supported: ${SUPPORTED_CHANNELS.join(', ')}`,
      'UNSUPPORTED_CHANNELS',
    );
  }

  // encoding
  if (typeof msg.encoding !== 'string') {
    throw new ProtocolError('Missing or invalid "encoding"', 'MISSING_ENCODING');
  }
  if (!(SUPPORTED_ENCODINGS as readonly string[]).includes(msg.encoding)) {
    throw new ProtocolError(
      `Unsupported encoding: ${msg.encoding}. Supported: ${SUPPORTED_ENCODINGS.join(', ')}`,
      'UNSUPPORTED_ENCODING',
    );
  }

  return {
    type: 'session.start',
    session_id: msg.session_id as string,
    source: msg.source as string,
    sample_rate: msg.sample_rate as number,
    channels: msg.channels as number,
    encoding: msg.encoding as SupportedEncoding,
  };
}

function parseSessionStop(msg: Record<string, unknown>): SessionStopMessage {
  if (typeof msg.session_id !== 'string' || msg.session_id.length === 0) {
    throw new ProtocolError('Missing or empty "session_id"', 'MISSING_SESSION_ID');
  }

  return {
    type: 'session.stop',
    session_id: msg.session_id as string,
  };
}
