"use client";

import { useQuery } from '@tanstack/react-query';
import { fetchStats } from '@/lib/api';
import { useGatewayStore } from '@/stores/gateway-store';
import { Activity, Copy, CheckCircle2, XCircle, Smartphone } from 'lucide-react';
import { useState } from 'react';

function StatCard({ title, value, sub }: { title: string, value: string | number, sub?: string }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <h3 className="text-sm font-medium text-slate-400 mb-2">{title}</h3>
      <div className="text-3xl font-bold text-slate-50">{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-2">{sub}</div>}
    </div>
  );
}

function LivePipeline() {
  const sessionsMap = useGatewayStore(s => s.sessions);
  const sessions = Object.values(sessionsMap);
  const chunks = useGatewayStore(s => s.chunks);

  if (sessions.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center text-slate-400">
        <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
        <p>No active calls.</p>
        <p className="text-sm">Waiting for incoming WebSocket connections...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {sessions.map(session => {
        const sessionChunks = chunks[session.sessionId] || [];
        const bufferPct = session.chunkBytes > 0 ? (session.bufferedBytes / session.chunkBytes) * 100 : 0;
        
        return (
          <div key={session.sessionId} className="bg-slate-900 border border-emerald-900/50 rounded-xl overflow-hidden relative shadow-lg shadow-emerald-900/20">
            <div className="absolute top-0 left-0 w-full h-1 bg-slate-800">
              <div 
                className="h-full bg-emerald-500 transition-all duration-100 ease-linear" 
                style={{ width: `${Math.min(100, bufferPct)}%` }} 
              />
            </div>
            
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h3 className="text-lg font-bold text-emerald-400 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    LIVE SESSION
                  </h3>
                  <p className="text-xs text-slate-500 font-mono mt-1">{session.sessionId}</p>
                </div>
                <div className="flex gap-6 text-sm">
                  <div><span className="text-slate-500">Vol:</span> {(session.rms || 0).toFixed(0)}</div>
                  <div><span className="text-slate-500">Bytes:</span> {(session.bytes / 1024).toFixed(1)} KB</div>
                  <div><span className="text-slate-500">Buffer:</span> {session.bufferedBytes} / {session.chunkBytes}</div>
                </div>
              </div>

              {/* Chunk Timeline */}
              <div className="mt-8 border-t border-slate-800 pt-6">
                <h4 className="text-xs font-semibold tracking-widest text-slate-500 mb-4 uppercase">Chunk Timeline</h4>
                <div className="flex gap-2 overflow-x-auto pb-4">
                  {sessionChunks.map(chunk => (
                    <div key={chunk.sequence} className="shrink-0 w-32 bg-slate-800 rounded-lg p-3 border border-slate-700">
                      <div className="text-xs text-slate-400 font-mono">CHUNK {chunk.sequence}</div>
                      <div className="text-sm font-medium mt-1">{chunk.durationMs}ms</div>
                      <div className="text-xs text-emerald-400 mt-2 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" /> SENT
                      </div>
                    </div>
                  ))}
                  {sessionChunks.length === 0 && (
                    <div className="text-xs text-slate-500 italic">No chunks emitted yet... buffering...</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function Overview() {
  const { data: stats } = useQuery({ queryKey: ['stats'], queryFn: fetchStats, refetchInterval: 5000 });
  const status = useGatewayStore(s => s.status);
  const network = useGatewayStore(s => s.network);
  
  const [copied, setCopied] = useState(false);

  const wsUrl = network ? `http://${network.recommendedIp}:${network.port}` : 'Waiting for network...';

  const copyUrl = () => {
    navigator.clipboard.writeText(wsUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="p-8 max-w-6xl mx-auto w-full space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Pipeline Overview</h1>
        <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold ${status === 'ONLINE' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
          <div className={`w-2 h-2 rounded-full ${status === 'ONLINE' ? 'bg-emerald-500' : 'bg-red-500'}`} />
          GATEWAY {status}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <StatCard title="Total Calls" value={stats?.totalCalls ?? '-'} />
        <StatCard title="Audio Processed" value={stats?.totalAudioBytes ? `${(stats.totalAudioBytes / 1024 / 1024).toFixed(2)} MB` : '-'} />
        <StatCard title="Chunks Emitted" value={stats?.totalChunks ?? '-'} />
        <StatCard title="Saved Recordings" value={stats?.recordings ?? '-'} sub={stats?.totalStorageBytes ? `${(stats.totalStorageBytes / 1024 / 1024).toFixed(2)} MB stored` : ''} />
      </div>

      <div className="bg-indigo-950/30 border border-indigo-900/50 rounded-xl p-6 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-indigo-500/20 rounded-full flex items-center justify-center text-indigo-400">
            <Smartphone className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-semibold text-indigo-300">Android Connection</h3>
            <p className="text-sm text-indigo-400/70 mt-1">Enter this URL in CallVault to connect</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <code className="bg-slate-900 px-4 py-2 rounded-lg font-mono text-emerald-400 border border-slate-800">
            {wsUrl}
          </code>
          <button 
            onClick={copyUrl}
            className="p-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg transition-colors text-white"
            title="Copy URL"
          >
            {copied ? <CheckCircle2 className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
          </button>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-bold mb-6">Live Media Pipeline</h2>
        <LivePipeline />
      </div>
    </div>
  );
}
