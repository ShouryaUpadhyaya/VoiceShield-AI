import { SystemStats, Call } from './types';

const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL || (typeof window !== 'undefined' ? `http://${window.location.hostname}:8010` : 'http://localhost:8010');
export async function fetchStats(): Promise<SystemStats> {
  const res = await fetch(`${GATEWAY_URL}/api/stats`);
  if (!res.ok) throw new Error('Failed to fetch stats');
  return res.json();
}

export async function fetchCalls(): Promise<Call[]> {
  const res = await fetch(`${GATEWAY_URL}/api/calls`);
  if (!res.ok) throw new Error('Failed to fetch calls');
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function fetchLogs(): Promise<any[]> {
  const res = await fetch(`${GATEWAY_URL}/api/logs`);
  if (!res.ok) throw new Error('Failed to fetch logs');
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function fetchCallDetails(id: string): Promise<Call> {
  const res = await fetch(`${GATEWAY_URL}/api/calls`);
  if (!res.ok) throw new Error('Failed to fetch call details');
  const calls: Call[] = await res.json();
  const call = calls.find(c => c.id === id);
  if (!call) throw new Error('Call not found');
  return call;
}

export function getRecordingUrl(callId: string): string {
  return `${GATEWAY_URL}/api/calls/${callId}/recording`;
}

export function getWebsocketUrl(): string {
  const url = new URL(GATEWAY_URL);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.pathname = '/dashboard';
  return url.toString();
}
