"use client";

import { useQuery } from '@tanstack/react-query';
import { fetchStats } from '@/lib/api';
import { useGatewayStore } from '@/stores/gateway-store';
import { Activity, Copy, CheckCircle2, XCircle, Smartphone, Server, Cpu, Database, Radio, Network, ArrowRight } from 'lucide-react';
import { useState, useEffect } from 'react';

function StatCard({ title, value, sub }: { title: string, value: string | number, sub?: string }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <h3 className="text-sm font-medium text-slate-400 mb-2">{title}</h3>
      <div className="text-3xl font-bold text-slate-50">{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-2">{sub}</div>}
    </div>
  );
}

function useMLStatus() {
  const [status, setStatus] = useState<any>(null);
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('http://localhost:8011/ready');
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
        } else {
          setStatus({ status: 'error', models: {} });
        }
      } catch (e) {
        setStatus({ status: 'offline', models: {} });
      }
    };
    fetchStatus();
    const int = setInterval(fetchStatus, 3000);
    return () => clearInterval(int);
  }, []);
  return status;
}

function ArchitecturePipeline() {
  const ml = useMLStatus();
  const sessionsMap = useGatewayStore(s => s.sessions);
  const isFlowing = Object.keys(sessionsMap).length > 0;

  const getModelColor = (modelStatus: string) => {
    if (modelStatus === 'OK') return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    if (modelStatus === 'UNAVAILABLE' || modelStatus === 'NOT_LOADED') return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    if (!ml || ml.status === 'offline') return 'bg-red-500/20 text-red-400 border-red-500/30';
    return 'bg-slate-800 text-slate-400 border-slate-700';
  };

  const getModelDot = (modelStatus: string) => {
    if (modelStatus === 'OK') return 'bg-emerald-500';
    if (modelStatus === 'UNAVAILABLE' || modelStatus === 'NOT_LOADED') return 'bg-amber-500';
    return 'bg-red-500';
  };

  const models = [
    { name: 'Dhwani (Anti-Spoof)', id: 'dhwani' },
    { name: 'Deepfake Predictor', id: 'deepfake' },
    { name: 'Prosody Analyzer', id: 'prosody' },
    { name: 'Speaker (ECAPA)', id: 'speaker' }
  ];

  return (
    <div className="mb-12 relative overflow-hidden bg-slate-950/50 backdrop-blur-3xl rounded-3xl border border-slate-800 p-8 shadow-2xl">
      {/* Background ambient glow based on flow */}
      <div className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[300px] blur-[120px] rounded-full pointer-events-none transition-all duration-1000 ${isFlowing ? 'bg-indigo-600/20' : 'bg-slate-800/20'}`} />
      
      <div className="flex flex-col md:flex-row items-center justify-between relative z-10 gap-8">
        
        {/* Node 1: Android Client */}
        <div className={`flex flex-col items-center gap-3 transition-transform duration-500 ${isFlowing ? 'scale-105' : 'scale-100'}`}>
          <div className={`w-24 h-24 rounded-2xl flex items-center justify-center border-2 transition-colors duration-500 shadow-lg ${isFlowing ? 'bg-indigo-900/40 border-indigo-500/50 shadow-indigo-500/20' : 'bg-slate-900 border-slate-800'}`}>
            <Smartphone className={`w-10 h-10 ${isFlowing ? 'text-indigo-400 animate-pulse' : 'text-slate-500'}`} />
          </div>
          <div className="text-center">
            <h4 className="font-bold text-slate-200">Android Client</h4>
            <p className="text-xs text-slate-500 font-mono mt-1">PCM16 • 48kHz</p>
          </div>
        </div>

        {/* Arrow 1 */}
        <div className="flex-1 flex items-center justify-center relative min-w-[50px]">
          <div className={`h-1 w-full rounded-full overflow-hidden ${isFlowing ? 'bg-indigo-900/30' : 'bg-slate-800'}`}>
            <div className={`h-full bg-indigo-500 w-1/2 ${isFlowing ? 'animate-[translateRight_1s_linear_infinite]' : 'hidden'}`} />
          </div>
          <ArrowRight className={`absolute w-6 h-6 ${isFlowing ? 'text-indigo-400' : 'text-slate-700'}`} />
        </div>

        {/* Node 2: Node.js Gateway */}
        <div className={`flex flex-col items-center gap-3 transition-transform duration-500 ${isFlowing ? 'scale-105' : 'scale-100'}`}>
          <div className={`w-28 h-28 rounded-2xl flex items-center justify-center border-2 transition-colors duration-500 shadow-lg relative ${isFlowing ? 'bg-cyan-900/40 border-cyan-500/50 shadow-cyan-500/20' : 'bg-slate-900 border-slate-800'}`}>
            <Network className={`w-12 h-12 ${isFlowing ? 'text-cyan-400' : 'text-slate-500'}`} />
            {isFlowing && <span className="absolute -top-2 -right-2 flex h-4 w-4"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span><span className="relative inline-flex rounded-full h-4 w-4 bg-cyan-500"></span></span>}
          </div>
          <div className="text-center">
            <h4 className="font-bold text-slate-200">Media Gateway</h4>
            <p className="text-xs text-slate-500 font-mono mt-1">Node.js • :8010</p>
          </div>
        </div>

        {/* Arrow 2 */}
        <div className="flex-1 flex items-center justify-center relative min-w-[50px]">
          <div className={`h-1 w-full rounded-full overflow-hidden ${isFlowing ? 'bg-cyan-900/30' : 'bg-slate-800'}`}>
            <div className={`h-full bg-cyan-500 w-1/2 ${isFlowing ? 'animate-[translateRight_1s_linear_infinite]' : 'hidden'}`} />
          </div>
          <ArrowRight className={`absolute w-6 h-6 ${isFlowing ? 'text-cyan-400' : 'text-slate-700'}`} />
        </div>

        {/* Node 3: ML Engine (Python) */}
        <div className={`flex flex-col items-center gap-3 transition-transform duration-500 min-w-[280px] ${isFlowing ? 'scale-105' : 'scale-100'}`}>
          <div className={`w-full rounded-2xl border-2 transition-colors duration-500 shadow-lg p-5 ${isFlowing ? 'bg-purple-900/20 border-purple-500/50 shadow-purple-500/20' : 'bg-slate-900 border-slate-800'}`}>
            <div className="flex items-center gap-3 mb-4 border-b border-slate-800/50 pb-3">
              <Cpu className={`w-8 h-8 ${isFlowing ? 'text-purple-400' : 'text-slate-500'}`} />
              <div>
                <h4 className="font-bold text-slate-200">ML Engine (Python)</h4>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${ml?.status === 'ready' ? 'bg-emerald-500' : ml?.status === 'offline' ? 'bg-red-500' : 'bg-amber-500'}`} />
                  <p className="text-xs text-slate-400 font-mono capitalize">{ml?.status || 'connecting...'}</p>
                </div>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-2">
              {models.map(model => {
                const s = ml?.models?.[model.id] || 'OFFLINE';
                return (
                  <div key={model.id} className={`flex flex-col justify-center px-3 py-2 rounded-lg border text-xs ${getModelColor(s)}`}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <div className={`w-1.5 h-1.5 rounded-full ${getModelDot(s)}`} />
                      <span className="font-bold truncate">{model.name}</span>
                    </div>
                    <span className="font-mono text-[9px] opacity-80 pl-3">{s}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

      </div>

      <style dangerouslySetInnerHTML={{__html: `
        @keyframes translateRight {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(200%); }
        }
      `}} />
    </div>
  );
}

function LivePipeline() {
  const sessionsMap = useGatewayStore(s => s.sessions);
  const sessions = Object.values(sessionsMap);
  const chunks = useGatewayStore(s => s.chunks);

  if (sessions.length === 0) {
    return (
      <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800/50 rounded-2xl p-16 text-center text-slate-400 shadow-2xl relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-purple-500/5 animate-pulse" />
        <Activity className="w-16 h-16 mx-auto mb-6 text-slate-600 opacity-50" />
        <p className="text-xl font-light tracking-wide text-slate-300">Awaiting Comm Link</p>
        <p className="text-sm mt-2 font-mono text-slate-500">WebSocket listener on port 8080 active...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {sessions.map(session => {
        const sessionChunks = chunks[session.sessionId] || [];
        const bufferPct = session.chunkBytes > 0 ? (session.bufferedBytes / session.chunkBytes) * 100 : 0;
        
        const deepfakeScores = sessionChunks.map(c => c.deepfakeScore).filter(s => s !== undefined) as number[];
        const aiLikelihood = deepfakeScores.length > 0 ? (deepfakeScores.reduce((a,b) => a+b, 0) / deepfakeScores.length) * 100 : null;
        
        const isSuspicious = aiLikelihood !== null && aiLikelihood > 50;

        return (
          <div key={session.sessionId} className={`relative bg-slate-950/80 backdrop-blur-3xl rounded-3xl overflow-hidden border shadow-2xl transition-all duration-1000 ${isSuspicious ? 'border-red-900/50 shadow-red-900/20' : 'border-emerald-900/50 shadow-emerald-900/20'}`}>
            
            {/* Animated Glow Background */}
            <div className={`absolute -top-40 -right-40 w-96 h-96 blur-3xl opacity-20 rounded-full pointer-events-none transition-colors duration-1000 ${isSuspicious ? 'bg-red-500' : 'bg-emerald-500'}`} />

            {/* Buffer Progress Bar */}
            <div className="absolute top-0 left-0 w-full h-1.5 bg-slate-900">
              <div 
                className={`h-full transition-all duration-100 ease-linear ${isSuspicious ? 'bg-red-500' : 'bg-emerald-500'}`}
                style={{ width: `${Math.min(100, bufferPct)}%` }} 
              />
            </div>
            
            <div className="p-8 relative z-10">
              {/* Header Section */}
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-8">
                <div>
                  <h3 className={`text-2xl font-black tracking-tight flex items-center gap-3 ${isSuspicious ? 'text-red-400' : 'text-emerald-400'}`}>
                    <span className={`w-3 h-3 rounded-full animate-pulse ${isSuspicious ? 'bg-red-500' : 'bg-emerald-500'}`} />
                    LIVE SESSION
                  </h3>
                  <p className="text-xs text-slate-500 font-mono mt-1 opacity-70">ID: {session.sessionId}</p>
                </div>
                
                <div className="flex gap-4">
                  <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 min-w-[140px]">
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Volume (RMS)</div>
                    <div className="text-xl font-mono text-white flex items-center gap-2">
                      {(session.rms || 0).toFixed(0)}
                      {/* Audio Pulse Visualizer based on RMS */}
                      <div className="flex gap-0.5 items-end h-4">
                        {[1, 2, 3].map(i => (
                          <div key={i} className="w-1 bg-indigo-500 rounded-t-sm transition-all duration-75" style={{ height: `${Math.min(100, ((session.rms||0)/500)*100 * (Math.random()*0.5+0.5))}%` }} />
                        ))}
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 min-w-[140px]">
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Data Ingested</div>
                    <div className="text-xl font-mono text-white">{(session.bytes / 1024).toFixed(1)} KB</div>
                  </div>

                  <div className={`border rounded-xl p-4 min-w-[160px] transition-colors duration-500 ${aiLikelihood !== null ? (isSuspicious ? 'bg-red-950/40 border-red-900/50' : 'bg-emerald-950/40 border-emerald-900/50') : 'bg-slate-900/80 border-slate-800'}`}>
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">AI Likelihood</div>
                    <div className={`text-3xl font-black font-mono ${aiLikelihood !== null ? (isSuspicious ? 'text-red-400' : 'text-emerald-400') : 'text-slate-400'}`}>
                      {aiLikelihood !== null ? `${aiLikelihood.toFixed(1)}%` : '--'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Chunk Timeline */}
              <div className="mt-8">
                <h4 className="text-xs font-semibold tracking-widest text-slate-500 mb-4 uppercase flex items-center gap-2">
                  <Activity className="w-4 h-4" /> Real-time ML Pipeline
                </h4>
                
                <div className="flex gap-4 overflow-x-auto pb-4 snap-x">
                  {sessionChunks.map(chunk => (
                    <div key={chunk.sequence} className="snap-start shrink-0 w-64 bg-slate-900/60 backdrop-blur-md rounded-2xl p-5 border border-slate-800/80 hover:border-indigo-500/50 transition-colors group">
                      <div className="text-xs text-slate-400 font-mono flex justify-between items-center mb-4">
                        <span className="bg-slate-800 px-2 py-1 rounded text-[10px]">CHUNK {chunk.sequence}</span>
                        <span>{chunk.durationMs}ms</span>
                      </div>
                      
                      <div className="space-y-3">
                        <div className="flex justify-between items-center text-sm">
                          <span className="text-slate-400">Deepfake Prob</span>
                          <span className={`font-mono font-bold ${chunk.mlStatus === 'PENDING' ? 'text-amber-400 animate-pulse' : (chunk.deepfakeScore != null ? (chunk.deepfakeScore > 0.5 ? 'text-red-400' : 'text-emerald-400') : 'text-slate-500')}`}>
                            {chunk.mlStatus === 'PENDING' ? 'ANALYZING...' : (chunk.deepfakeScore != null ? `${(chunk.deepfakeScore * 100).toFixed(1)}%` : 'N/A')}
                          </span>
                        </div>
                        
                        <div className="flex justify-between items-center text-sm">
                          <span className="text-slate-400">Prosody Risk</span>
                          <span className={`font-mono font-bold ${chunk.mlStatus === 'PENDING' ? 'text-amber-400 animate-pulse' : (chunk.anomalyScore !== undefined ? (chunk.anomalyScore > 0.5 ? 'text-red-400' : 'text-emerald-400') : 'text-slate-500')}`}>
                            {chunk.mlStatus === 'PENDING' ? '...' : (chunk.anomalyScore !== undefined ? `${(chunk.anomalyScore * 100).toFixed(1)}%` : 'N/A')}
                          </span>
                        </div>
                        
                        <div className="flex justify-between items-center text-sm">
                          <span className="text-slate-400">ECAPA Speaker</span>
                          <span className={`font-mono ${chunk.mlStatus === 'PENDING' ? 'text-amber-400 animate-pulse' : (chunk.speakerMatch === 'matched' ? 'text-emerald-400' : chunk.speakerMatch === 'unmatched' ? 'text-red-400' : 'text-indigo-400')}`}>
                            {chunk.mlStatus === 'PENDING' ? '...' : (chunk.speakerMatch || 'N/A')}
                          </span>
                        </div>

                        {chunk.latencyMs !== undefined && (
                          <div className="flex justify-between items-center text-xs pt-1 border-t border-slate-800">
                            <span className="text-slate-500">Latency</span>
                            <span className="font-mono text-slate-500">{chunk.latencyMs.toFixed(0)} ms</span>
                          </div>
                        )}
                      </div>
                      
                      {/* Decorative progress line */}
                      <div className="w-full h-1 bg-slate-800 rounded-full mt-5 overflow-hidden">
                        <div className={`h-full rounded-full ${chunk.mlStatus === 'PENDING' ? 'w-1/2 bg-amber-500 animate-ping' : 'w-full bg-emerald-500 opacity-50 group-hover:opacity-100 transition-opacity'}`} />
                      </div>
                    </div>
                  ))}
                  {sessionChunks.length === 0 && (
                    <div className="w-full h-32 border border-dashed border-slate-700 rounded-2xl flex items-center justify-center text-slate-500 italic text-sm">
                      Buffering initial audio chunk...
                    </div>
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

      <ArchitecturePipeline />

      <div>
        <h2 className="text-lg font-bold mb-6">Live Media Pipeline</h2>
        <LivePipeline />
      </div>
    </div>
  );
}
