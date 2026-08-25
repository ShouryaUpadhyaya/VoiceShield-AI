import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useCallSecurity } from '../../state/callSecurity';
import { RiskGauge } from '../../components/RiskGauge/RiskGauge';
import { LiveWaveform } from '../../components/LiveWaveform/LiveWaveform';
import { SecurityAlert } from '../../components/SecurityAlert/SecurityAlert';
import { TechnicalSignals } from '../../components/TechnicalSignals/TechnicalSignals';
import { LiveRiskChart } from '../../components/LiveRiskChart';
import { PhoneCall, LayoutDashboard, Shield, Clock, User, ArrowLeft, Loader2, ServerOff } from 'lucide-react';
import { verifyCaller } from '../../api/calls';

export function LiveCall() {
  const { id } = useParams();
  const { state, connect, disconnect } = useCallSecurity();
  const [chartData, setChartData] = useState<{time: string, risk: number}[]>([]);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<string | null>(null);

  useEffect(() => {
    // Connect to WS when entering this view, especially if it's the demo
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  useEffect(() => {
    if (state.riskScore !== undefined) {
       const now = new Date();
       setChartData(prev => {
          const newData = [...prev, {
            time: now.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            risk: state.riskScore
          }];
          return newData.slice(-30); // keep last 30 points
       });
    }
  }, [state.riskScore]);

  const handleVerify = async () => {
    setVerifying(true);
    const success = await verifyCaller(state.callId, "MFA");
    setVerifying(false);
    setVerifyResult(success ? "Verification Challenge Sent to Trusted Device" : "Verification Failed");
    setTimeout(() => setVerifyResult(null), 5000);
  };

  const handleEscalate = () => {
    setVerifyResult("Call Escalated to Security Supervisor");
    setTimeout(() => setVerifyResult(null), 5000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans p-4 md:p-8">
      
      {/* Header */}
      <header className="mb-6 flex flex-col md:flex-row justify-between md:items-center gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-black tracking-tight text-white flex items-center gap-3">
            <Link to="/" className="p-2 hover:bg-slate-800 rounded-lg transition-colors mr-2">
              <ArrowLeft className="w-5 h-5 text-slate-400" />
            </Link>
            <PhoneCall className="w-6 h-6 md:w-8 md:h-8 text-indigo-500" />
            Live Verification <span className="text-slate-500 font-normal">| {id === 'demo' ? 'Demo Mode' : state.callId || 'Connecting...'}</span>
          </h1>
        </div>
        
        <div className="flex items-center gap-4">
           {/* Connection Status Indicator */}
           <div className={`px-3 py-1.5 rounded-full text-xs font-bold flex items-center gap-2 border ${
             state.connectionStatus === 'CONNECTED' ? 'bg-emerald-950/40 text-emerald-400 border-emerald-900/50' :
             state.connectionStatus === 'CONNECTING' ? 'bg-blue-950/40 text-blue-400 border-blue-900/50' :
             state.connectionStatus === 'DEGRADED' ? 'bg-yellow-950/40 text-yellow-400 border-yellow-900/50' :
             'bg-red-950/40 text-red-400 border-red-900/50'
           }`}>
             {state.connectionStatus === 'CONNECTED' ? <Shield className="w-3 h-3" /> : 
              state.connectionStatus === 'CONNECTING' ? <Loader2 className="w-3 h-3 animate-spin" /> :
              <ServerOff className="w-3 h-3" />}
             {state.connectionStatus}
           </div>

           <Link to="/" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg font-bold text-white transition-all flex items-center gap-2 border border-slate-700 text-sm">
            <LayoutDashboard className="w-4 h-4" />
            <span className="hidden md:inline">Dashboard</span>
          </Link>
        </div>
      </header>

      {/* Main Content */}
      {state.connectionStatus === 'DISCONNECTED' ? (
         <div className="flex flex-col items-center justify-center h-64 bg-slate-900 border border-slate-800 rounded-2xl border-dashed">
            <ServerOff className="w-12 h-12 text-slate-600 mb-4" />
            <p className="text-slate-400 font-medium text-lg">AI monitoring unavailable</p>
            <p className="text-slate-500 text-sm mt-2">Unable to complete voice integrity verification.</p>
         </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Left Column: Caller Info & Waveform & Chart */}
          <div className="lg:col-span-2 flex flex-col gap-6">
            
            {/* Caller Info Card */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
               <div className="flex items-center gap-4">
                  <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center border border-slate-700">
                     <User className="w-8 h-8 text-slate-400" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-white">{state.claimedIdentity || "Unknown Caller"}</h2>
                    <p className="text-slate-400 font-mono text-sm">{state.caller || "+-- --- --- ----"}</p>
                  </div>
               </div>
               <div className="flex items-center gap-2 text-slate-400 bg-slate-950 px-4 py-2 rounded-lg border border-slate-800">
                  <Clock className="w-4 h-4 text-indigo-400" />
                  <span className="font-mono font-medium">Live Stream</span>
               </div>
            </div>

            {/* Live Waveform */}
            <LiveWaveform isActive={state.connectionStatus === 'CONNECTED' && !!state.callId} riskScore={state.riskScore} />

            {/* Risk History Chart */}
            <div className="h-[300px]">
               <LiveRiskChart data={chartData} />
            </div>

          </div>

          {/* Right Column: Risk Gauge & Signals & Alerts */}
          <div className="flex flex-col gap-6">
            <RiskGauge score={state.riskScore} level={state.riskLevel} />
            
            <TechnicalSignals state={state} />

            {/* Action Buttons (Always available but change style based on risk) */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col gap-3">
               <h3 className="text-slate-400 font-semibold mb-2 text-sm tracking-wider uppercase">Actions</h3>
               {verifying || verifyResult ? (
                 <div className={`w-full py-3.5 rounded-xl font-bold text-center border flex items-center justify-center gap-2 ${verifyResult ? 'bg-indigo-900/30 text-indigo-300 border-indigo-800' : 'bg-slate-800 text-slate-300 border-slate-700'}`}>
                    {verifying ? <Loader2 className="w-5 h-5 animate-spin" /> : <Shield className="w-5 h-5" />}
                    {verifying ? 'Sending Challenge...' : verifyResult}
                 </div>
               ) : (
                 <>
                   <button onClick={handleVerify} className="w-full py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl transition-colors shadow-lg shadow-indigo-900/20 border border-indigo-500">
                     Verify Caller Identity
                   </button>
                   <button onClick={handleEscalate} className="w-full py-3.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold rounded-xl transition-colors border border-slate-700">
                     Escalate to Supervisor
                   </button>
                   {state.riskLevel === 'CRITICAL' && (
                     <button className="w-full py-3.5 bg-red-900/50 hover:bg-red-900 text-red-400 font-bold rounded-xl transition-colors border border-red-800 mt-2">
                       DO NOT AUTHORIZE
                     </button>
                   )}
                 </>
               )}
            </div>
          </div>
          
        </div>
      )}

      {/* Critical Security Alert overlays at bottom */}
      <div className="fixed bottom-0 left-0 right-0 p-4 md:p-8 z-50 pointer-events-none flex justify-center">
         <div className="pointer-events-auto w-full max-w-5xl">
            <SecurityAlert alert={state.alert} onVerify={handleVerify} onEscalate={handleEscalate} />
         </div>
      </div>

    </div>
  );
}
