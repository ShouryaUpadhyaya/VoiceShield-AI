"use client";

import { useQuery } from '@tanstack/react-query';
import { fetchAudit, fetchCallDetails, getRecordingUrl, verifyIntegrity } from '@/lib/api';
import { useParams } from 'next/navigation';
import { Download, PlayCircle, ArrowLeft, Clock, FileAudio, Server, ShieldCheck } from 'lucide-react';
import Link from 'next/link';
import { use, useState } from 'react';

export default function CallDetail({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const { id } = resolvedParams;
  
  const { data: call, isLoading, error } = useQuery({ 
    queryKey: ['call', id], 
    queryFn: () => fetchCallDetails(id),
    retry: false
  });
  const { data: audit, refetch: refetchAudit } = useQuery({ queryKey: ['audit', id], queryFn: () => fetchAudit(id), retry: false });
  const [verification, setVerification] = useState<any>(null);

  if (isLoading) return <div className="p-8 text-slate-400">Loading call details...</div>;
  if (error || !call) return <div className="p-8 text-red-400">Call not found or database offline.</div>;

  const stream = call.audio_streams?.[0];
  const recording = call.recordings?.[0];
  const audioUrl = getRecordingUrl(call.id);

  return (
    <div className="p-8 max-w-4xl mx-auto w-full space-y-6">
      <Link href="/calls" className="text-sm text-indigo-400 hover:text-indigo-300 flex items-center gap-2 mb-6 w-fit">
        <ArrowLeft className="w-4 h-4" /> Back to History
      </Link>

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Call Details</h1>
        <span className={`px-3 py-1 rounded-full text-xs font-bold border uppercase ${call.status === 'COMPLETED' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'}`}>
          {call.status}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-widest flex items-center gap-2 mb-4">
            <Server className="w-4 h-4" /> Metadata
          </h2>
          
          <div>
            <div className="text-xs text-slate-500">Call ID</div>
            <div className="font-mono text-sm">{call.id}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Session ID</div>
            <div className="font-mono text-sm text-slate-300">{call.session_id}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Source</div>
            <div className="text-sm uppercase text-indigo-400">{call.source}</div>
          </div>
          <div className="grid grid-cols-2 gap-4 pt-2">
            <div>
              <div className="text-xs text-slate-500 flex items-center gap-1"><Clock className="w-3 h-3" /> Started</div>
              <div className="text-sm">{new Date(call.created_at).toLocaleString()}</div>
            </div>
            {call.ended_at && (
              <div>
                <div className="text-xs text-slate-500 flex items-center gap-1"><Clock className="w-3 h-3" /> Ended</div>
                <div className="text-sm">{new Date(call.ended_at).toLocaleString()}</div>
              </div>
            )}
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-widest flex items-center gap-2 mb-4">
            <FileAudio className="w-4 h-4" /> Audio Pipeline
          </h2>

          {stream ? (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-slate-500">Format</div>
                <div className="text-sm uppercase">{stream.encoding}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Sample Rate</div>
                <div className="text-sm font-mono">{stream.sample_rate} Hz</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Channels</div>
                <div className="text-sm">{stream.channels === 1 ? 'Mono' : 'Stereo'}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Total Processed</div>
                <div className="text-sm font-mono text-emerald-400">{(stream.bytes_received / 1024).toFixed(1)} KB</div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-slate-500 italic">No audio stream data recorded.</div>
          )}
        </div>
      </div>

      {recording ? (
        <div className="bg-indigo-950/20 border border-indigo-900/40 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-indigo-300 uppercase tracking-widest flex items-center gap-2 mb-6">
            <PlayCircle className="w-4 h-4" /> Recording
          </h2>
          
          <div className="flex flex-col md:flex-row items-center gap-6">
            <audio controls className="w-full h-12" src={audioUrl}>
              Your browser does not support the audio element.
            </audio>
            
            <a 
              href={audioUrl} 
              download={`${call.id}.wav`}
              className="shrink-0 flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
            >
              <Download className="w-4 h-4" /> Download WAV
            </a>
          </div>
          <div className="mt-4 text-xs text-slate-500 font-mono">
            Size: {(recording.size_bytes / 1024).toFixed(1)} KB | Duration: {(recording.duration_ms / 1000).toFixed(1)}s
          </div>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-500">
          <FileAudio className="w-8 h-8 mx-auto mb-3 opacity-30" />
          <p>No WAV recording available for this call.</p>
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-widest flex items-center gap-2">
              <ShieldCheck className="w-4 h-4" /> Audit Integrity
            </h2>
            <p className="text-xs text-slate-500 mt-2">AI estimates whether audio is likely synthetic. This check only verifies whether the stored evidence and recorded result changed after anchoring.</p>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs font-bold border ${audit?.state === 'VERIFIED' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : audit?.state === 'MISMATCH' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'}`}>{audit?.state === 'VERIFIED' ? 'BLOCKCHAIN VERIFIED' : audit?.state ?? 'NOT ANCHORED'}</span>
        </div>
        {audit?.evidence_hash && <div className="text-xs font-mono text-slate-400 break-all">Evidence hash: {audit.evidence_hash}</div>}
        {audit?.transaction_hash && <div className="text-xs font-mono text-slate-400 break-all">Transaction: {audit.transaction_hash} · Block {audit.block_number} · {audit.blockchain_network}</div>}
        <button className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-sm font-medium" onClick={async () => { setVerification(await verifyIntegrity(id)); await refetchAudit(); }}>Verify Integrity</button>
        {verification && <div className={`text-sm ${verification.verified ? 'text-emerald-400' : 'text-red-400'}`}>{verification.verified ? '✓ Blockchain Verified: current evidence matches the anchored record.' : `✗ Integrity check failed: ${verification.status}`}</div>}
      </div>
    </div>
  );
}
