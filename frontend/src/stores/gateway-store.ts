import { create } from 'zustand';
import { GatewayStatus, LiveSession, NetworkInfo, Chunk } from '../lib/types';
import { io, Socket } from 'socket.io-client';

interface GatewayState {
  status: GatewayStatus;
  network: NetworkInfo | null;
  sessions: Record<string, LiveSession>;
  chunks: Record<string, Chunk[]>; // sessionId -> Chunk[]
  
  setStatus: (status: GatewayStatus) => void;
  setNetwork: (network: NetworkInfo) => void;
  updateSession: (sessionId: string, data: Partial<LiveSession>) => void;
  addChunk: (sessionId: string, chunk: Chunk) => void;
  removeSession: (sessionId: string) => void;
  connectWebsocket: (url: string) => void;
  disconnectWebsocket: () => void;
}

let socket: Socket | null = null;

export const useGatewayStore = create<GatewayState>((set, get) => ({
  status: 'OFFLINE',
  network: null,
  sessions: {},
  chunks: {},

  setStatus: (status) => set({ status }),
  setNetwork: (network) => set({ network }),

  updateSession: (sessionId, data) => set((state) => ({
    sessions: {
      ...state.sessions,
      [sessionId]: {
        ...(state.sessions[sessionId] || { 
          sessionId, status: 'STREAMING', rms: 0, bytes: 0, bufferedBytes: 0, chunkBytes: 96000, chunksEmitted: 0 
        }),
        ...data,
      }
    }
  })),

  addChunk: (sessionId, chunk) => set((state) => {
    const existing = state.chunks[sessionId] || [];
    // Deduplicate by sequence
    if (existing.some(c => c.sequence === chunk.sequence)) {
      return state;
    }
    return {
      chunks: {
        ...state.chunks,
        [sessionId]: [...existing, chunk].slice(-20) // Keep last 20 chunks for visualization
      }
    };
  }),

  removeSession: (sessionId) => set((state) => {
    const { [sessionId]: _, ...restSessions } = state.sessions;
    const { [sessionId]: __, ...restChunks } = state.chunks;
    return { sessions: restSessions, chunks: restChunks };
  }),

  connectWebsocket: (url) => {
    if (socket) return;
    // Replace ws:// with http:// for socket.io since it upgrades over HTTP
    const httpUrl = url.replace('ws://', 'http://').replace('wss://', 'https://');
    
    // Connect specifically to the /dashboard namespace
    const ioSocket = io(httpUrl.endsWith('/dashboard') ? httpUrl : `${httpUrl}/dashboard`, {
      transports: ['websocket'] // optional: force websocket transport
    });
    socket = ioSocket;
    
    ioSocket.on('connect', () => {
      if (socket === ioSocket) set({ status: 'ONLINE' });
    });
    
    ioSocket.on('disconnect', () => {
      if (socket === ioSocket) {
        set({ status: 'OFFLINE' });
      }
    });
    
    ioSocket.on('gateway_state', (msg) => {
      if (socket !== ioSocket) return;
      get().setNetwork(msg.network);
      get().setStatus('ONLINE');
    });

    ioSocket.on('stats', (msg) => {
      if (socket !== ioSocket) return;
      get().updateSession(msg.session_id, {
        status: msg.status,
        rms: msg.rms,
        bytes: msg.bytes,
        bufferedBytes: msg.buffered_bytes,
        chunkBytes: msg.chunk_bytes,
        chunksEmitted: msg.chunks_emitted
      });
    });

    ioSocket.on('chunk_created', (msg) => {
      if (socket !== ioSocket) return;
      get().addChunk(msg.session_id, {
        sequence: msg.sequence,
        bytes: msg.bytes,
        durationMs: msg.durationMs,
        timestampMs: msg.timestampMs,
        mlStatus: 'SENT'
      });
    });

    ioSocket.on('session.stopped', (msg) => {
      if (socket !== ioSocket) return;
      get().updateSession(msg.session_id, { status: 'COMPLETED' });
      setTimeout(() => get().removeSession(msg.session_id), 10000); // clear after 10s
    });
  },

  disconnectWebsocket: () => {
    if (socket) {
      const s = socket;
      socket = null;
      s.disconnect();
    }
  }
}));
