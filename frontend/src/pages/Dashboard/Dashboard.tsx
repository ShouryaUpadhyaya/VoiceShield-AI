import React, { useState, useEffect } from 'react';
import { Shield, Users, AlertTriangle, PhoneCall, ShieldAlert, Activity, ArrowRight, LayoutDashboard } from 'lucide-react';
import { Link } from 'react-router-dom';
import { DashboardCallSummary, fetchActiveCalls } from '../../api/calls';

export function Dashboard() {
  const [activeCalls, setActiveCalls] = useState<DashboardCallSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadCalls = async () => {
      const calls = await fetchActiveCalls();
      setActiveCalls(calls);
      setLoading(false);
    };
    loadCalls();
  }, []);

  const highRiskCount = activeCalls.filter(c => c.riskLevel === 'HIGH' || c.riskLevel === 'CRITICAL').length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans p-8">
      <header className="mb-10 flex justify-between items-center border-b border-slate-800 pb-6">
        <div>
          <h1 className="text-4xl font-black tracking-tight text-white flex items-center gap-4">
            <Shield className="w-10 h-10 text-indigo-500" />
            VoiceGuard <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">Security Center</span>
          </h1>
          <p className="text-slate-400 mt-2 text-lg">Real-Time Voice Impersonation Prevention</p>
        </div>
      </header>

      {/* High-level metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex items-center gap-6">
          <div className="p-4 bg-indigo-900/30 rounded-xl">
            <Users className="w-8 h-8 text-indigo-400" />
          </div>
          <div>
            <p className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-1">Total Verifications</p>
            <p className="text-3xl font-black text-white">1,248</p>
          </div>
        </div>

        <div className={`bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex items-center gap-6 ${highRiskCount > 0 ? 'border-red-900/50 relative overflow-hidden' : ''}`}>
          {highRiskCount > 0 && <div className="absolute inset-0 bg-red-900/10 animate-pulse"></div>}
          <div className={`p-4 rounded-xl z-10 ${highRiskCount > 0 ? 'bg-red-900/50' : 'bg-slate-800'}`}>
            <ShieldAlert className={`w-8 h-8 ${highRiskCount > 0 ? 'text-red-400' : 'text-slate-400'}`} />
          </div>
          <div className="z-10">
            <p className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-1">High-Risk Events</p>
            <p className={`text-3xl font-black ${highRiskCount > 0 ? 'text-red-400' : 'text-white'}`}>{highRiskCount}</p>
          </div>
        </div>
        
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex items-center gap-6">
          <div className="p-4 bg-blue-900/30 rounded-xl">
            <PhoneCall className="w-8 h-8 text-blue-400" />
          </div>
          <div>
            <p className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-1">Active Calls</p>
            <p className="text-3xl font-black text-white">{activeCalls.length}</p>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex items-center gap-6">
          <div className="p-4 bg-emerald-900/30 rounded-xl">
            <Activity className="w-8 h-8 text-emerald-400" />
          </div>
          <div>
            <p className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-1">AI Node Health</p>
            <p className="text-3xl font-black text-emerald-400">100%</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        
        <div className="lg:col-span-3 bg-slate-900 border border-slate-800 rounded-2xl shadow-xl overflow-hidden">
          <div className="p-6 border-b border-slate-800 flex justify-between items-center bg-slate-950/50">
            <h2 className="text-xl font-bold flex items-center gap-3">
              <Activity className="w-5 h-5 text-indigo-400" />
              Active Verification Sessions
            </h2>
            <Link to="/live/demo" className="text-sm font-bold text-indigo-400 bg-indigo-900/20 px-4 py-2 rounded-lg hover:bg-indigo-900/40 transition-colors border border-indigo-900/50 flex items-center gap-2">
              Start Demo Mode <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-slate-900 text-slate-400 text-xs uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th className="px-6 py-4 font-semibold">Caller Identity</th>
                  <th className="px-6 py-4 font-semibold">Risk Level</th>
                  <th className="px-6 py-4 font-semibold">Score</th>
                  <th className="px-6 py-4 font-semibold">Duration</th>
                  <th className="px-6 py-4 font-semibold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {loading ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-slate-500">Loading active sessions...</td>
                  </tr>
                ) : (
                  activeCalls.map(call => (
                    <tr key={call.id} className={`hover:bg-slate-800/30 transition-colors ${call.riskLevel === 'CRITICAL' ? 'bg-red-950/10' : ''}`}>
                      <td className="px-6 py-5 font-medium">{call.caller}</td>
                      <td className="px-6 py-5">
                        <span className={`px-3 py-1 text-xs font-bold rounded-full ${
                          call.riskLevel === 'CRITICAL' ? 'bg-red-900/50 text-red-400 border border-red-800' : 
                          call.riskLevel === 'HIGH' ? 'bg-orange-900/50 text-orange-400 border border-orange-800' :
                          call.riskLevel === 'MEDIUM' ? 'bg-yellow-900/50 text-yellow-400 border border-yellow-800' : 
                          'bg-emerald-900/50 text-emerald-400 border border-emerald-800'
                        }`}>
                          {call.riskLevel}
                        </span>
                      </td>
                      <td className="px-6 py-5 font-mono">
                         <div className="flex items-center gap-2">
                           <div className={`w-8 h-2 rounded-full ${call.riskLevel === 'CRITICAL' ? 'bg-red-500' : call.riskLevel === 'HIGH' ? 'bg-orange-500' : call.riskLevel === 'MEDIUM' ? 'bg-yellow-500' : 'bg-emerald-500'}`} style={{width: `${Math.max(10, call.score)}%`, maxWidth: '60px'}}></div>
                           <span className={call.riskLevel === 'CRITICAL' ? 'text-red-400' : ''}>{call.score}</span>
                         </div>
                      </td>
                      <td className="px-6 py-5 text-slate-400 text-sm">{call.duration}</td>
                      <td className="px-6 py-5">
                        <Link to={`/live/${call.id}`} className="text-indigo-400 hover:text-indigo-300 font-semibold text-sm flex items-center gap-1">
                          View Details <ArrowRight className="w-4 h-4" />
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-xl p-6">
           <h3 className="text-lg font-bold mb-6 flex items-center gap-2 border-b border-slate-800 pb-4">
             <AlertTriangle className="w-5 h-5 text-slate-400" />
             Recent Incidents
           </h3>
           <div className="space-y-4">
              <div className="p-4 rounded-xl border border-red-900/30 bg-red-950/10 hover:bg-red-950/20 transition-colors cursor-pointer">
                 <div className="flex justify-between items-start mb-2">
                    <span className="font-semibold text-red-400 text-sm">Synthetic Voice Detected</span>
                    <span className="text-xs text-slate-500">10m ago</span>
                 </div>
                 <p className="text-sm text-slate-300">Target: High-value wire transfer approval.</p>
                 <span className="inline-block mt-3 text-xs bg-red-900/40 text-red-300 px-2 py-1 rounded border border-red-800">BLOCKED</span>
              </div>
              
              <div className="p-4 rounded-xl border border-orange-900/30 bg-orange-950/10 hover:bg-orange-950/20 transition-colors cursor-pointer">
                 <div className="flex justify-between items-start mb-2">
                    <span className="font-semibold text-orange-400 text-sm">Prosody Mismatch</span>
                    <span className="text-xs text-slate-500">1h ago</span>
                 </div>
                 <p className="text-sm text-slate-300">Target: Account password reset.</p>
                 <span className="inline-block mt-3 text-xs bg-slate-800 text-slate-300 px-2 py-1 rounded border border-slate-700">ESCALATED</span>
              </div>
           </div>
        </div>

      </div>
    </div>
  );
}
