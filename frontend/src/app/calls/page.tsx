"use client";

import { useQuery } from '@tanstack/react-query';
import { fetchCalls, getRecordingUrl } from '@/lib/api';
import { formatDistanceToNow } from 'date-fns';
import { PlayCircle, Download, FileText } from 'lucide-react';
import Link from 'next/link';

export default function CallHistory() {
  const { data: calls, isLoading, error } = useQuery({ queryKey: ['calls'], queryFn: fetchCalls, refetchInterval: 5000 });

  if (isLoading) {
    return <div className="p-8 text-slate-400">Loading call history...</div>;
  }

  if (error) {
    return <div className="p-8 text-red-400">Failed to load calls. Database might be offline.</div>;
  }

  if (!calls || calls.length === 0) {
    return (
      <div className="p-8">
        <h1 className="text-2xl font-bold mb-6">Call History</h1>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center text-slate-400">
          <HistoryIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No historical calls found.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto w-full">
      <h1 className="text-2xl font-bold mb-6">Call History</h1>
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-800 text-slate-400">
            <tr>
              <th className="px-6 py-4 font-medium">Date</th>
              <th className="px-6 py-4 font-medium">Source</th>
              <th className="px-6 py-4 font-medium">Duration</th>
              <th className="px-6 py-4 font-medium">Audio Processed</th>
              <th className="px-6 py-4 font-medium">Status</th>
              <th className="px-6 py-4 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {calls.map((call) => {
              const stream = call.audio_streams?.[0];
              const recording = call.recordings?.[0];
              
              return (
                <tr key={call.id} className="hover:bg-slate-800/50 transition-colors">
                  <td className="px-6 py-4">
                    <div className="font-medium">{new Date(call.created_at).toLocaleDateString()}</div>
                    <div className="text-slate-500 text-xs">{new Date(call.created_at).toLocaleTimeString()}</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="bg-indigo-500/10 text-indigo-400 px-2 py-1 rounded text-xs border border-indigo-500/20 uppercase">
                      {call.source}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono text-slate-300">
                    {call.duration_ms > 0 ? `${(call.duration_ms / 1000).toFixed(1)}s` : '-'}
                  </td>
                  <td className="px-6 py-4 font-mono text-slate-300">
                    {stream?.bytes_received ? `${(stream.bytes_received / 1024).toFixed(1)} KB` : '-'}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded text-xs border uppercase ${call.status === 'COMPLETED' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'}`}>
                      {call.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right space-x-3">
                    <Link href={`/calls/${call.id}`} className="text-slate-400 hover:text-white transition-colors" title="View Details">
                      <FileText className="w-5 h-5 inline" />
                    </Link>
                    {recording && (
                      <a href={getRecordingUrl(call.id)} download={`${call.id}.wav`} className="text-indigo-400 hover:text-indigo-300 transition-colors" title="Download WAV">
                        <Download className="w-5 h-5 inline" />
                      </a>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function HistoryIcon(props: any) {
  return (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
      <path d="M3 3v5h5"/>
      <path d="M12 7v5l4 2"/>
    </svg>
  );
}
