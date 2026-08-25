import { create } from 'zustand';
import { GatewayStatus, LiveSession, NetworkInfo, Chunk } from '../lib/types';

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

let ws: WebSocket | null = null;

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
    if (ws) return;
    const socket = new WebSocket(url);
    ws = socket;
    
    socket.onopen = () => {
      if (ws === socket) set({ status: 'ONLINE' });
    };
    
    socket.onclose = () => {
      if (ws === socket) {
        set({ status: 'OFFLINE' });
        ws = null;
        setTimeout(() => get().connectWebsocket(url), 2000); // auto reconnect
      }
    };
    
    socket.onmessage = (event) => {
      if (ws !== socket) return;
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'gateway_state') {
          get().setNetwork(msg.network);
          get().setStatus('ONLINE');
        } else if (msg.type === 'stats') {
          get().updateSession(msg.session_id, {
            status: msg.status,
            rms: msg.rms,
            bytes: msg.bytes,
            bufferedBytes: msg.buffered_bytes,
            chunkBytes: msg.chunk_bytes,
            chunksEmitted: msg.chunks_emitted
          });
        } else if (msg.type === 'chunk_created') {
          get().addChunk(msg.session_id, {
            sequence: msg.sequence,
            bytes: msg.bytes,
            durationMs: msg.durationMs,
            timestampMs: msg.timestampMs,
            mlStatus: 'SENT'
          });
        } else if (msg.type === 'session.stopped') {
          get().updateSession(msg.session_id, { status: 'COMPLETED' });
          setTimeout(() => get().removeSession(msg.session_id), 10000); // clear after 10s
        }
      } catch (err) {
        console.error('WS Parse Error', err);
      }
    };
  },

  disconnectWebsocket: () => {
    if (ws) {
      const socket = ws;
      ws = null;
      socket.close();
    }
  }
}));
