"use client";

import { useEffect, useState } from 'react';
import { MlApi } from '@/lib/mlApi';
import { FileAudio, ChevronRight, Activity, Calendar } from 'lucide-react';
import Link from 'next/link';

export default function TestHistoryPage() {
  const [tests, setTests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    MlApi.getTestHistory()
      .then(data => setTests(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-8 max-w-6xl mx-auto w-full">
      <div className="flex items-center gap-2 text-sm text-slate-500 mb-6">
        <Link href="/models" className="hover:text-slate-300 transition-colors">ML Model Lab</Link>
        <ChevronRight className="w-4 h-4" />
        <span className="text-slate-300">Test History</span>
      </div>

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-100 mb-2">Model Test History</h1>
          <p className="text-slate-400">Log of all isolated file tests and pipeline runs.</p>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        {loading ? (
          <div className="p-12 flex justify-center text-slate-500"><Activity className="w-8 h-8 animate-spin" /></div>
        ) : tests.length === 0 ? (
          <div className="p-12 flex justify-center text-slate-500">No tests found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/50">
                  <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Date</th>
                  <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">File</th>
                  <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Model/Pipeline</th>
                  <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Score</th>
                  <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Latency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {tests.map(test => (
                  <tr key={test.id} className="hover:bg-slate-800/20 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 text-sm text-slate-300">
                        <Calendar className="w-4 h-4 text-slate-500" />
                        {new Date(test.created_at).toLocaleString()}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded bg-slate-800 flex items-center justify-center">
                          <FileAudio className="w-4 h-4 text-indigo-400" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-200">{test.filename}</p>
                          <p className="text-xs text-slate-500">{test.duration ? `${test.duration.toFixed(1)}s` : 'Unknown length'}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {test.is_pipeline ? (
                        <span className="px-2 py-1 bg-purple-500/10 text-purple-400 text-xs font-semibold rounded uppercase">Full Pipeline</span>
                      ) : (
                        <span className="px-2 py-1 bg-slate-800 text-slate-300 text-xs font-semibold rounded uppercase">{test.model}</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 rounded text-xs font-semibold uppercase ${test.status === 'success' ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'}`}>
                        {test.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {test.final_score !== null ? (
                        <span className={`text-sm font-bold ${test.final_score > 0.5 ? 'text-amber-400' : 'text-emerald-400'}`}>
                          {(test.final_score * 100).toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-slate-500 text-sm">—</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm font-mono text-slate-400">{test.latency_ms} ms</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
