import React, { useState, useEffect } from 'react';
import { Shield, Users, AlertTriangle, PhoneCall, ShieldAlert, Activity } from 'lucide-react';
import { Link } from 'react-router-dom';

interface CallSession {
  id: string;
  caller: string;
  duration: string;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH';
  score: number;
}

// Mock active calls for the dashboard overview
const MOCK_CALLS: CallSession[] = [
  { id: '1001', caller: '+91 98765 43210', duration: '04:12', riskLevel: 'LOW', score: 12 },
  { id: '1002', caller: '+91 87654 32109', duration: '01:45', riskLevel: 'MEDIUM', score: 68 },
  { id: '1003', caller: '+1 415 555 0198', duration: '00:30', riskLevel: 'HIGH', score: 92 },
  { id: '1004', caller: '+44 20 7123 4567', duration: '12:05', riskLevel: 'LOW', score: 5 },
];

export function SecurityDashboard() {
  const [activeCalls, setActiveCalls] = useState<CallSession[]>(MOCK_CALLS);

  // In a real app, we would connect to a websocket here to get live updates
  // of all active calls.

  const highRiskCount = activeCalls.filter(c => c.riskLevel === 'HIGH').length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans p-8">
      <header className="mb-10 flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-black tracking-tight text-white flex items-center gap-4">
            <Shield className="w-10 h-10 text-indigo-500" />
            VoiceShield <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">Command Center</span>
          </h1>
          <p className="text-slate-400 mt-2 text-lg">Global Multi-Layer Voice Authenticity Overview</p>
        </div>
        <Link to="/agent" className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 rounded-xl font-bold text-white transition-all shadow-lg shadow-indigo-900/50 flex items-center gap-2">
          <PhoneCall className="w-5 h-5" />
          Switch to Agent View
        </Link>
      </header>

      {/* High-level metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex items-center gap-6">
          <div className="p-4 bg-indigo-900/30 rounded-xl">
            <Users className="w-8 h-8 text-indigo-400" />
          </div>
          <div>
            <p className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-1">Active Sessions</p>
            <p className="text-4xl font-black text-white">{activeCalls.length}</p>
          </div>
        </div>

        <div className={`bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex items-center gap-6 ${highRiskCount > 0 ? 'border-red-900/50 relative overflow-hidden' : ''}`}>
          {highRiskCount > 0 && <div className="absolute inset-0 bg-red-900/10 animate-pulse"></div>}
          <div className={`p-4 rounded-xl z-10 ${highRiskCount > 0 ? 'bg-red-900/50' : 'bg-slate-800'}`}>
            <ShieldAlert className={`w-8 h-8 ${highRiskCount > 0 ? 'text-red-400' : 'text-slate-400'}`} />
          </div>
          <div className="z-10">
            <p className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-1">Critical Threats</p>
            <p className={`text-4xl font-black ${highRiskCount > 0 ? 'text-red-400' : 'text-white'}`}>{highRiskCount}</p>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex items-center gap-6">
          <div className="p-4 bg-emerald-900/30 rounded-xl">
            <Activity className="w-8 h-8 text-emerald-400" />
          </div>
          <div>
            <p className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-1">System Health</p>
            <p className="text-4xl font-black text-emerald-400">100%</p>
          </div>
        </div>
      </div>

      {/* Active Calls Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-xl overflow-hidden">
        <div className="p-6 border-b border-slate-800">
          <h2 className="text-xl font-bold flex items-center gap-3">
            <PhoneCall className="w-5 h-5 text-indigo-400" />
            Live Monitored Calls
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-slate-950/50 text-slate-400 text-sm uppercase tracking-wider">
              <tr>
                <th className="px-6 py-4 font-semibold">Session ID</th>
                <th className="px-6 py-4 font-semibold">Caller ID</th>
                <th className="px-6 py-4 font-semibold">Duration</th>
                <th className="px-6 py-4 font-semibold">Risk Score</th>
                <th className="px-6 py-4 font-semibold">Status</th>
                <th className="px-6 py-4 font-semibold">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {activeCalls.map(call => (
                <tr key={call.id} className={`hover:bg-slate-800/50 transition-colors ${call.riskLevel === 'HIGH' ? 'bg-red-950/10' : ''}`}>
                  <td className="px-6 py-5 font-mono text-slate-300">{call.id}</td>
                  <td className="px-6 py-5 font-medium">{call.caller}</td>
                  <td className="px-6 py-5 text-slate-400">{call.duration}</td>
                  <td className="px-6 py-5">
                    <div className="flex items-center gap-3">
                      <div className="w-full bg-slate-800 rounded-full h-2.5 max-w-[100px]">
                        <div 
                          className={`h-2.5 rounded-full ${call.riskLevel === 'HIGH' ? 'bg-red-500' : call.riskLevel === 'MEDIUM' ? 'bg-yellow-500' : 'bg-emerald-500'}`} 
                          style={{ width: `${call.score}%` }}
                        ></div>
                      </div>
                      <span className="font-mono">{call.score}%</span>
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <span className={`px-3 py-1 text-xs font-bold rounded-full ${
                      call.riskLevel === 'HIGH' ? 'bg-red-900/50 text-red-400 border border-red-800' : 
                      call.riskLevel === 'MEDIUM' ? 'bg-yellow-900/50 text-yellow-400 border border-yellow-800' : 
                      'bg-emerald-900/50 text-emerald-400 border border-emerald-800'
                    }`}>
                      {call.riskLevel}
                    </span>
                  </td>
                  <td className="px-6 py-5">
                    <Link to="/agent" className="text-indigo-400 hover:text-indigo-300 font-semibold text-sm flex items-center gap-1">
                      Monitor <Activity className="w-4 h-4" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
