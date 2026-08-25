import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, ShieldAlert, PhoneCall, Activity, Plus, Trash2, ShieldCheck, AlertTriangle } from 'lucide-react';
import { useDemoSimulation, DemoCall } from '../../hooks/useDemoSimulation';

export function DemoDashboard() {
  const {
    activeCalls,
    totalVerifications,
    nodeHealth,
    injectSpamCall,
    injectCleanCall,
    injectSuspiciousCall,
    clearAll,
    resolveCall
  } = useDemoSimulation();

  const highRiskCount = activeCalls.filter(c => c.riskLevel === 'HIGH' || c.riskLevel === 'CRITICAL').length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans p-4 md:p-8 flex flex-col md:flex-row gap-6 selection:bg-indigo-500/30">
      
      {/* Left Column: Believable Output (75%) */}
      <div className="flex-1 flex flex-col gap-6">
        <header className="flex justify-between items-center border-b border-slate-800/60 pb-6">
          <div>
            <h1 className="text-4xl font-black tracking-tight text-white flex items-center gap-4">
              <motion.div 
                animate={{ rotate: [0, 15, -15, 0] }}
                transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
              >
                <Shield className="w-10 h-10 text-indigo-500 drop-shadow-[0_0_15px_rgba(99,102,241,0.5)]" />
              </motion.div>
              VoiceGuard <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-cyan-400">Live Demo</span>
            </h1>
            <p className="text-slate-400 mt-2 text-lg">Real-Time Voice Impersonation Prevention - Simulated Environment</p>
          </div>
        </header>

        {/* Top Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <MetricCard title="Total Verifications" value={totalVerifications.toLocaleString()} icon={<Activity className="w-6 h-6 text-indigo-400" />} />
          <MetricCard title="Active Calls" value={activeCalls.length} icon={<PhoneCall className="w-6 h-6 text-blue-400" />} />
          <MetricCard 
            title="High-Risk Events" 
            value={highRiskCount} 
            icon={<ShieldAlert className={`w-6 h-6 ${highRiskCount > 0 ? 'text-red-400' : 'text-slate-400'}`} />} 
            isAlert={highRiskCount > 0} 
          />
          <MetricCard title="AI Node Health" value={`${nodeHealth.toFixed(1)}%`} icon={<ShieldCheck className="w-6 h-6 text-emerald-400" />} />
        </div>

        {/* Live Call Feed */}
        <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800/80 rounded-2xl shadow-2xl flex-1 flex flex-col overflow-hidden relative">
          {/* Subtle grid background */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#4f4f4f2e_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f2e_1px,transparent_1px)] bg-[size:14px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] pointer-events-none"></div>

          <div className="p-6 border-b border-slate-800/60 bg-slate-900/80 backdrop-blur-md z-10 flex justify-between items-center">
            <h2 className="text-xl font-bold flex items-center gap-3">
              <Activity className="w-5 h-5 text-indigo-400 animate-pulse" />
              Live Verification Feed
            </h2>
            <span className="text-xs font-mono bg-indigo-500/20 text-indigo-300 px-3 py-1 rounded-full border border-indigo-500/30">
              {activeCalls.length} Active Sessions
            </span>
          </div>

          <div className="p-6 overflow-y-auto flex-1 z-10 space-y-4">
            <AnimatePresence>
              {activeCalls.length === 0 ? (
                <motion.div 
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="h-full flex flex-col items-center justify-center text-slate-500 gap-4"
                >
                  <PhoneCall className="w-12 h-12 opacity-20" />
                  <p>No active calls in simulation.</p>
                </motion.div>
              ) : (
                activeCalls.map(call => (
                  <CallRow key={call.id} call={call} onResolve={() => resolveCall(call.id)} />
                ))
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* Right Column: Control Panel (25%) */}
      <div className="w-full md:w-80 bg-slate-900/40 backdrop-blur-xl border border-slate-800/80 rounded-2xl p-6 shadow-2xl flex flex-col gap-6">
        <div>
          <h2 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
            Control Panel
          </h2>
          <p className="text-sm text-slate-400">Inject events to simulate system behavior.</p>
        </div>

        <div className="space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Inject Events</h3>
          <ControlButton 
            onClick={injectCleanCall} 
            icon={<PhoneCall className="w-4 h-4" />} 
            label="Inject Clean Call" 
            color="emerald" 
          />
          <ControlButton 
            onClick={injectSuspiciousCall} 
            icon={<AlertTriangle className="w-4 h-4" />} 
            label="Inject Suspicious Call" 
            color="orange" 
          />
          <ControlButton 
            onClick={injectSpamCall} 
            icon={<ShieldAlert className="w-4 h-4" />} 
            label="Inject Critical Scam" 
            color="red" 
          />
        </div>

        <div className="mt-auto space-y-3 pt-6 border-t border-slate-800/60">
           <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Global Actions</h3>
           <button 
             onClick={clearAll}
             className="w-full py-3 px-4 rounded-xl flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium transition-all text-sm border border-slate-700 hover:border-slate-600"
           >
             <Trash2 className="w-4 h-4" /> Clear All Sessions
           </button>
        </div>
      </div>

    </div>
  );
}

function MetricCard({ title, value, icon, isAlert = false }: { title: string, value: string | number, icon: React.ReactNode, isAlert?: boolean }) {
  return (
    <div className={`relative overflow-hidden rounded-2xl p-5 border ${isAlert ? 'bg-red-950/20 border-red-900/50' : 'bg-slate-900/50 border-slate-800/60'} backdrop-blur-sm shadow-xl`}>
      {isAlert && <div className="absolute inset-0 bg-red-900/10 animate-pulse pointer-events-none"></div>}
      <div className="flex items-center gap-4 relative z-10">
        <div className={`p-3 rounded-xl ${isAlert ? 'bg-red-900/40' : 'bg-slate-800/80'}`}>
          {icon}
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">{title}</p>
          <p className={`text-2xl font-black ${isAlert ? 'text-red-400 drop-shadow-[0_0_8px_rgba(248,113,113,0.5)]' : 'text-white'}`}>{value}</p>
        </div>
      </div>
    </div>
  );
}

function ControlButton({ onClick, icon, label, color }: { onClick: () => void, icon: React.ReactNode, label: string, color: 'emerald' | 'red' | 'orange' }) {
  const colorStyles = {
    emerald: "bg-emerald-950/30 text-emerald-400 hover:bg-emerald-900/50 border-emerald-900/50 hover:border-emerald-500/50",
    red: "bg-red-950/30 text-red-400 hover:bg-red-900/50 border-red-900/50 hover:border-red-500/50",
    orange: "bg-orange-950/30 text-orange-400 hover:bg-orange-900/50 border-orange-900/50 hover:border-orange-500/50"
  };

  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className={`w-full py-3 px-4 rounded-xl flex items-center gap-3 font-medium transition-all text-sm border shadow-lg ${colorStyles[color]}`}
    >
      <div className="bg-black/20 p-1.5 rounded-md">{icon}</div>
      {label}
    </motion.button>
  );
}

function CallRow({ call, onResolve }: { call: DemoCall, onResolve: () => void }) {
  const isCritical = call.riskLevel === 'CRITICAL';
  const isHigh = call.riskLevel === 'HIGH';
  const isSafe = call.riskLevel === 'SAFE';

  const rowStyles = isCritical 
    ? 'bg-red-950/20 border-red-900/40' 
    : isHigh 
    ? 'bg-orange-950/20 border-orange-900/40' 
    : 'bg-slate-900/40 border-slate-800/40';

  const badgeStyles = isCritical
    ? 'bg-red-900/50 text-red-400 border border-red-800 shadow-[0_0_10px_rgba(248,113,113,0.3)]'
    : isHigh
    ? 'bg-orange-900/50 text-orange-400 border border-orange-800'
    : 'bg-emerald-900/50 text-emerald-400 border border-emerald-800';

  return (
    <motion.div
      initial={{ opacity: 0, y: -20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95, x: 50 }}
      transition={{ type: "spring", stiffness: 300, damping: 25 }}
      className={`flex flex-col md:flex-row md:items-center justify-between p-5 rounded-xl border backdrop-blur-sm gap-4 ${rowStyles}`}
    >
      <div className="flex items-center gap-4">
        <div className="relative">
           {isCritical && (
             <motion.div 
               animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }} 
               transition={{ duration: 2, repeat: Infinity }} 
               className="absolute inset-0 bg-red-500 rounded-full" 
             />
           )}
           <div className={`relative z-10 w-10 h-10 rounded-full flex items-center justify-center border ${isCritical ? 'bg-red-950 border-red-800' : isHigh ? 'bg-orange-950 border-orange-800' : 'bg-slate-800 border-slate-700'}`}>
              <PhoneCall className={`w-4 h-4 ${isCritical ? 'text-red-400' : isHigh ? 'text-orange-400' : 'text-slate-400'}`} />
           </div>
        </div>
        <div>
          <p className="font-bold text-white text-lg">{call.caller}</p>
          <div className="flex flex-wrap items-center gap-2 mt-1">
             <span className="text-xs text-slate-400 font-mono">{call.id}</span>
             <span className="text-slate-600">•</span>
             <span className="text-xs text-slate-400">{call.duration}</span>
             {call.issue && (
               <>
                 <span className="text-slate-600">•</span>
                 <span className={`text-xs font-semibold ${isCritical ? 'text-red-400' : 'text-orange-400'}`}>
                   Issue: {call.issue}
                 </span>
               </>
             )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex flex-col items-end gap-2">
          <span className={`px-3 py-1 text-[10px] font-black uppercase tracking-widest rounded-full ${badgeStyles}`}>
            {call.riskLevel}
          </span>
          <div className="flex items-center gap-2">
            <div className="w-24 h-1.5 bg-slate-800 rounded-full overflow-hidden">
               <motion.div 
                 initial={{ width: 0 }}
                 animate={{ width: `${call.score}%` }}
                 className={`h-full ${isCritical ? 'bg-red-500 shadow-[0_0_10px_rgba(248,113,113,0.8)]' : isHigh ? 'bg-orange-500' : 'bg-emerald-500'}`} 
               />
            </div>
            <span className="text-xs font-mono text-slate-400 w-6 text-right">{call.score}</span>
          </div>
        </div>
        <button 
          onClick={onResolve}
          className="p-2 hover:bg-slate-800 rounded-lg transition-colors text-slate-500 hover:text-white"
          title="Resolve / Dismiss"
        >
          <Trash2 className="w-5 h-5" />
        </button>
      </div>
    </motion.div>
  );
}
