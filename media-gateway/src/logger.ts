/**
 * Structured Logger
 *
 * Simple, clear structured logging with event types and session context.
 * No external dependencies — just formatted console output.
 */

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const LOG_LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

let currentLevel: LogLevel = 'info';

export function setLogLevel(level: LogLevel): void {
  currentLevel = level;
}

function shouldLog(level: LogLevel): boolean {
  return LOG_LEVELS[level] >= LOG_LEVELS[currentLevel];
}

function timestamp(): string {
  return new Date().toISOString().slice(11, 23); // HH:MM:SS.mmm
}

function format(level: LogLevel, event: string, data?: Record<string, unknown>): string {
  const parts = [`[${timestamp()}]`, event.toUpperCase()];
  if (data) {
    for (const [key, value] of Object.entries(data)) {
      parts.push(`${key}=${value}`);
    }
  }
  return parts.join(' ');
}

export const logger = {
  debug(event: string, data?: Record<string, unknown>): void {
    if (shouldLog('debug')) console.debug(format('debug', event, data));
  },

  info(event: string, data?: Record<string, unknown>): void {
    if (shouldLog('info')) console.log(format('info', event, data));
  },

  warn(event: string, data?: Record<string, unknown>): void {
    if (shouldLog('warn')) console.warn(format('warn', event, data));
  },

  error(event: string, data?: Record<string, unknown>): void {
    if (shouldLog('error')) console.error(format('error', event, data));
  },
};
