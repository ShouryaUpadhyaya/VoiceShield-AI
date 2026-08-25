"use client";

import { useQuery } from '@tanstack/react-query';
import { fetchLogs } from '@/lib/api';
import { Activity, ShieldAlert, LogIn, LogOut, CheckCircle } from 'lucide-react';

export default function Events() {
  const { data: logs, isLoading, error } = useQuery({ queryKey: ['logs'], queryFn: fetchLogs, refetchInterval: 5000 });

  if (isLoading) return <div className="p-8 text-slate-400">Loading system events...</div>;
  if (error) return <div className="p-8 text-red-400">Failed to load system events.</div>;

  const getEventIcon = (type: string) => {
    if (type.includes('START')) return <LogIn className="w-4 h-4 text-emerald-400" />;
    if (type.includes('STOP')) return <LogOut className="w-4 h-4 text-rose-400" />;
    if (type.includes('ERROR')) return <ShieldAlert className="w-4 h-4 text-red-500" />;
    return <CheckCircle className="w-4 h-4 text-indigo-400" />;
  };

  return (
    <div className="p-8 max-w-6xl mx-auto w-full">
      <div className="flex items-center gap-3 mb-6">
        <Activity className="w-6 h-6 text-indigo-400" />
        <h1 className="text-2xl font-bold">System Events</h1>
      </div>
      
      {logs && logs.length > 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-800 text-slate-400">
              <tr>
                <th className="px-6 py-4 font-medium">Timestamp</th>
                <th className="px-6 py-4 font-medium">Event Type</th>
                <th className="px-6 py-4 font-medium">Call ID</th>
                <th className="px-6 py-4 font-medium">Session ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {logs.map((log: any) => (
                <tr key={log.id} className="hover:bg-slate-800/50 transition-colors">
                  <td className="px-6 py-4 font-mono text-slate-400 text-xs">
                    {new Date(log.timestamp).toLocaleString()}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      {getEventIcon(log.event_type)}
                      <span className="font-semibold text-slate-300">{log.event_type}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 font-mono text-xs text-indigo-300">
                    {log.call_id || '-'}
                  </td>
                  <td className="px-6 py-4 font-mono text-xs text-slate-500">
                    {log.session_id || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center text-slate-500">
          <p>No events recorded in the system yet.</p>
        </div>
      )}
    </div>
  );
}
