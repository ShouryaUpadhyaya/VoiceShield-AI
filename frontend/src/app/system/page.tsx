"use client";

import { useQuery } from '@tanstack/react-query';
import { fetchStats } from '@/lib/api';
import { HardDrive, Activity, PhoneCall, Database, Clock } from 'lucide-react';

export default function System() {
  const { data: stats, isLoading, error } = useQuery({ queryKey: ['stats'], queryFn: fetchStats, refetchInterval: 5000 });

  if (isLoading) return <div className="p-8 text-slate-400">Loading system stats...</div>;
  if (error) return <div className="p-8 text-red-400">Failed to load system stats.</div>;

  const metrics = [
    { label: 'Total Calls Processed', value: stats?.totalCalls || 0, icon: PhoneCall, color: 'text-indigo-400' },
    { label: 'Audio Chunks Stored', value: stats?.totalChunks || 0, icon: Database, color: 'text-emerald-400' },
    { label: 'Audio Data Processed', value: `${((stats?.totalAudioBytes || 0) / 1024 / 1024).toFixed(2)} MB`, icon: Activity, color: 'text-amber-400' },
    { label: 'WAV Recordings', value: stats?.recordings || 0, icon: HardDrive, color: 'text-rose-400' },
    { label: 'Storage Used', value: `${((stats?.totalStorageBytes || 0) / 1024 / 1024).toFixed(2)} MB`, icon: Clock, color: 'text-cyan-400' }
  ];

  return (
    <div className="p-8 max-w-6xl mx-auto w-full space-y-8">
      <h1 className="text-2xl font-bold">System Metrics</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {metrics.map((m, i) => {
          const Icon = m.icon;
          return (
            <div key={i} className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col justify-between hover:border-slate-700 transition-colors">
              <div className="flex items-start justify-between mb-4">
                <div className="text-sm font-medium text-slate-400">{m.label}</div>
                <div className={`p-2 rounded-lg bg-slate-800/50 ${m.color}`}>
                  <Icon className="w-5 h-5" />
                </div>
              </div>
              <div className="text-3xl font-bold font-mono tracking-tight">{m.value}</div>
            </div>
          );
        })}
      </div>
      
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 className="text-lg font-bold mb-4">Storage Breakdown</h2>
        <div className="w-full bg-slate-800 rounded-full h-4 overflow-hidden flex">
          <div className="bg-indigo-500 h-full" style={{ width: '40%' }}></div>
          <div className="bg-emerald-500 h-full" style={{ width: '30%' }}></div>
          <div className="bg-amber-500 h-full" style={{ width: '20%' }}></div>
          <div className="bg-rose-500 h-full" style={{ width: '10%' }}></div>
        </div>
        <div className="flex items-center gap-6 mt-4 text-xs font-medium text-slate-400">
          <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-indigo-500"></div> PostgreSQL DB</div>
          <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-emerald-500"></div> WAV Recordings</div>
          <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-amber-500"></div> ML Models</div>
          <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-rose-500"></div> Logs</div>
        </div>
      </div>
    </div>
  );
}
