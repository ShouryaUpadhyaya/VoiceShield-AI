import React, { useState, useEffect, useRef } from 'react';
import { Upload, Shield, AlertTriangle, ShieldAlert, Lock, Fingerprint, Waveform, Activity, PhoneCall, LayoutDashboard, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { LiveRiskChart } from '../components/LiveRiskChart';

export function AgentView() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [verificationState, setVerificationState] = useState<'IDLE' | 'PENDING' | 'VERIFYING' | 'COMPLETED'>('IDLE');
  const [chartData, setChartData] = useState<{time: string, risk: number}[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setResult(null);
      setVerificationState('IDLE');
      setChartData([]);
    }
  };

  const handleSimulateStream = async () => {
    if (!file) return;
    setLoading(true);
    setResult(null);
    setChartData([]);
    
    // For demo purposes, we can either use the WS or the REST endpoint.
    // Let's use the REST endpoint to get the final score, and animate the chart
    // to simulate a live call analysis.
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('http://localhost:8000/api/analyze/audio', formData);
      const data = response.data;
      
      // Simulate real-time streaming updates on the chart
      let currentRisk = 0;
      const targetRisk = data.risk_assessment.risk_score;
      const steps = 10;
      let step = 0;

      const interval = setInterval(() => {
        step++;
        currentRisk += (targetRisk - currentRisk) * 0.5; // Ease towards target
        
        const now = new Date();
        setChartData(prev => [...prev, {
          time: now.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          risk: Math.round(currentRisk)
        }]);

        if (step >= steps) {
          clearInterval(interval);
          setResult(data);
          setLoading(false);
          if (data.prevention_status.verification_required.length > 0) {
            setVerificationState('PENDING');
          }
        }
      }, 500);

    } catch (error) {
      console.error(error);
      setLoading(false);
      alert('Analysis failed. Ensure backend is running.');
    }
  };

  const handleVerification = () => {
    setVerificationState('VERIFYING');
    setTimeout(() => {
      setVerificationState('COMPLETED');
    }, 2000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans p-8">
      <header className="mb-8 flex justify-between items-center border-b border-slate-800 pb-6">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-white flex items-center gap-3">
            <PhoneCall className="w-8 h-8 text-indigo-500" />
            Agent View <span className="text-slate-500 font-normal">| Live Call Analysis</span>
          </h1>
          <p className="text-slate-400 mt-2 text-md">Analyze incoming audio streams for AI synthesis artifacts</p>
        </div>
        <Link to="/" className="px-5 py-2 bg-slate-800 hover:bg-slate-700 rounded-xl font-bold text-white transition-all flex items-center gap-2 border border-slate-700">
          <LayoutDashboard className="w-5 h-5" />
          Dashboard Overview
        </Link>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: Input & Chart */}
        <div className="lg:col-span-2 space-y-8">
          <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
             <div className="border-2 border-dashed border-slate-700 rounded-2xl p-8 hover:border-indigo-500 transition-colors bg-slate-950/50 group relative cursor-pointer">
                <input
                  type="file"
                  accept="audio/*"
                  onChange={handleFileChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                />
                <div className="flex flex-col items-center justify-center text-center gap-4">
                  <div className="p-4 bg-slate-800 rounded-full group-hover:bg-indigo-900/30 transition-colors">
                    <Upload className="w-8 h-8 text-indigo-400" />
                  </div>
                  <span className="text-lg font-semibold text-slate-200">
                    {file ? file.name : "Upload Call Recording or Sample"}
                  </span>
                </div>
              </div>

              <button
                onClick={handleSimulateStream}
                disabled={!file || loading}
                className="mt-6 w-full py-4 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50 disabled:cursor-not-allowed font-bold flex justify-center items-center gap-3 transition-all shadow-lg"
              >
                {loading ? <Loader2 className="animate-spin w-5 h-5" /> : <Activity className="w-5 h-5" />}
                {loading ? "Simulating Live Analysis..." : "Start Analysis"}
              </button>
          </div>

          <LiveRiskChart data={chartData} />
        </div>

        {/* Right Column: Results */}
        <div>
          {!result && !loading && (
             <div className="h-full bg-slate-900/50 border border-slate-800 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center opacity-50">
               <Shield className="w-16 h-16 text-slate-600 mb-4" />
               <p className="text-slate-400 font-medium">Awaiting call stream...</p>
             </div>
          )}

          {result && (
            <div className="animate-in fade-in slide-in-from-right-8 duration-500 space-y-6">
              
              {/* Alert Box */}
              <div className={`p-6 rounded-2xl border-2 flex flex-col gap-4 ${
                result.risk_assessment.risk_level === 'HIGH' ? 'bg-red-950/40 border-red-900/80 text-red-100 shadow-[0_0_30px_-5px_rgba(220,38,38,0.3)]' :
                result.risk_assessment.risk_level === 'MEDIUM' ? 'bg-yellow-950/40 border-yellow-900/80 text-yellow-100' :
                'bg-emerald-950/40 border-emerald-900/80 text-emerald-100'
              }`}>
                <div className="flex items-center gap-4">
                  {result.risk_assessment.risk_level === 'HIGH' ? <ShieldAlert className="w-12 h-12 text-red-500" /> :
                   result.risk_assessment.risk_level === 'MEDIUM' ? <AlertTriangle className="w-12 h-12 text-yellow-500" /> :
                   <Shield className="w-12 h-12 text-emerald-500" />}
                  <div>
                    <h3 className="text-2xl font-black tracking-tight">
                      {result.risk_assessment.risk_level === 'HIGH' ? 'CRITICAL RISK' :
                       result.risk_assessment.risk_level === 'MEDIUM' ? 'VERIFICATION REQ' :
                       'SECURE'}
                    </h3>
                    <p className="opacity-90 text-sm mt-1">{result.prevention_status.status.replace(/_/g, ' ')}</p>
                  </div>
                </div>
              </div>

              {/* Signals */}
              <div className="space-y-4">
                <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <Activity className="w-5 h-5 text-cyan-400" />
                    <span className="font-semibold text-slate-300">Deepfake Probability</span>
                  </div>
                  <span className="text-xl font-mono font-bold text-cyan-400">{(result.signals.deepfake_probability * 100).toFixed(1)}%</span>
                </div>

                <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <Fingerprint className="w-5 h-5 text-purple-400" />
                    <span className="font-semibold text-slate-300">Speaker Match</span>
                  </div>
                  <span className={`text-xl font-mono font-bold ${result.signals.speaker_match < 0.5 ? 'text-red-400' : 'text-purple-400'}`}>
                    {(result.signals.speaker_match * 100).toFixed(1)}%
                  </span>
                </div>
                
                <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <Waveform className="w-5 h-5 text-pink-400" />
                    <span className="font-semibold text-slate-300">Prosody Anomaly</span>
                  </div>
                  <span className="text-xl font-mono font-bold text-pink-400">{(result.signals.prosody_analysis.overall_prosody_risk * 100).toFixed(1)}%</span>
                </div>
              </div>

              {/* Actions */}
              {verificationState === 'PENDING' && (
                <button
                  onClick={handleVerification}
                  className="w-full py-4 bg-red-600 hover:bg-red-500 text-white font-bold rounded-xl flex justify-center items-center gap-2 transition-all shadow-lg"
                >
                  <Lock className="w-5 h-5" />
                  Initiate {result.prevention_status.verification_required.join(' and ')}
                </button>
              )}
              {verificationState === 'VERIFYING' && (
                <div className="w-full flex justify-center items-center gap-3 text-red-300 font-semibold px-4 py-4 bg-red-900/30 rounded-xl border border-red-900/50">
                  <Loader2 className="animate-spin w-5 h-5" />
                  Sending MFA Challenge...
                </div>
              )}
              {verificationState === 'COMPLETED' && (
                <div className="w-full flex justify-center items-center gap-3 text-emerald-400 font-bold px-4 py-4 bg-emerald-950/50 rounded-xl border border-emerald-900/50">
                  <Shield className="w-5 h-5" />
                  Secondary Verification Passed
                </div>
              )}

            </div>
          )}
        </div>

      </div>
    </div>
  );
}
