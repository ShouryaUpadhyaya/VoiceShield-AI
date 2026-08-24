import React, { useState } from 'react';
import axios from 'axios';
import { Shield, ShieldAlert, Upload, Activity, Loader2, Fingerprint, Waveform, AlertTriangle } from 'lucide-react';

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setResult(null);
    }
  };

  const handleAnalyze = async () => {
    if (!file) return;
    
    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('http://localhost:8000/api/analyze/audio', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      setResult(response.data);
    } catch (error) {
      console.error('Error analyzing audio:', error);
      alert('Failed to connect to the backend. Is it running?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen p-8 flex flex-col items-center bg-slate-950 text-slate-50 font-sans">
      <header className="mb-10 text-center mt-6">
        <div className="flex justify-center items-center gap-3 mb-4">
          <Shield className="w-14 h-14 text-indigo-500" />
          <h1 className="text-5xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 via-purple-400 to-cyan-400">
            VoiceShield AI
          </h1>
        </div>
        <p className="text-slate-400 max-w-xl mx-auto text-lg">Multi-Signal Intelligence: Detecting AI deepfakes, verifying speaker identity, and analyzing behavioral prosody in real-time.</p>
      </header>

      <main className="w-full max-w-5xl bg-slate-900 rounded-3xl border border-slate-800 p-8 shadow-2xl">
        
        {/* Upload Section */}
        <div className="border-2 border-dashed border-slate-700 rounded-2xl p-10 text-center hover:bg-slate-800/50 transition-colors group">
          <input 
            type="file" 
            id="audio-upload" 
            accept="audio/*" 
            className="hidden" 
            onChange={handleFileChange}
          />
          <label htmlFor="audio-upload" className="cursor-pointer flex flex-col items-center gap-4">
            <div className="p-4 bg-slate-800 rounded-full group-hover:bg-indigo-900/30 transition-colors">
              <Upload className="w-10 h-10 text-indigo-400" />
            </div>
            <span className="text-xl font-semibold text-slate-200">
              {file ? file.name : "Select Audio Sample for Analysis"}
            </span>
            <span className="text-sm text-slate-500 font-medium">Supports WAV, MP3, M4A</span>
          </label>
        </div>

        <button 
          onClick={handleAnalyze}
          disabled={!file || loading}
          className="mt-6 w-full py-4 rounded-2xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50 disabled:cursor-not-allowed font-bold text-lg flex justify-center items-center gap-3 shadow-lg shadow-indigo-900/20 transition-all"
        >
          {loading ? <Loader2 className="animate-spin w-6 h-6" /> : <Activity className="w-6 h-6" />}
          {loading ? "Running Multi-Signal Fusion..." : "Initiate Full Risk Analysis"}
        </button>

        {/* Results Section */}
        {result && (
          <div className="mt-10 animate-in fade-in slide-in-from-bottom-8 duration-700">
            <h2 className="text-2xl font-bold mb-6 flex items-center gap-2 border-b border-slate-800 pb-4">
              Intelligence Report
            </h2>
            
            {/* 4 Cards for Signals */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 shadow-inner flex flex-col justify-between">
                <div className="flex items-center gap-2 mb-3 text-slate-400">
                  <Activity className="w-4 h-4 text-cyan-400" />
                  <span className="text-xs font-semibold uppercase tracking-wider">Deepfake Prob</span>
                </div>
                <p className="text-3xl font-mono text-cyan-400">{(result.signals.deepfake_probability * 100).toFixed(0)}%</p>
              </div>

              <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 shadow-inner flex flex-col justify-between">
                <div className="flex items-center gap-2 mb-3 text-slate-400">
                  <Fingerprint className="w-4 h-4 text-purple-400" />
                  <span className="text-xs font-semibold uppercase tracking-wider">Speaker Match</span>
                </div>
                <p className={`text-3xl font-mono ${result.signals.speaker_match < 0.5 ? 'text-red-400' : 'text-purple-400'}`}>
                  {(result.signals.speaker_match * 100).toFixed(0)}%
                </p>
              </div>

              <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 shadow-inner flex flex-col justify-between">
                <div className="flex items-center gap-2 mb-3 text-slate-400">
                  <Waveform className="w-4 h-4 text-pink-400" />
                  <span className="text-xs font-semibold uppercase tracking-wider">Prosody Risk</span>
                </div>
                <p className="text-3xl font-mono text-pink-400">{(result.signals.prosody_analysis.overall_prosody_risk * 100).toFixed(0)}%</p>
              </div>

              <div className="bg-indigo-950/30 p-5 rounded-2xl border border-indigo-900/50 shadow-inner flex flex-col justify-between relative overflow-hidden">
                <div className="absolute -right-4 -top-4 opacity-10">
                  <Shield className="w-24 h-24" />
                </div>
                <div className="flex items-center gap-2 mb-3 text-indigo-300 z-10">
                  <AlertTriangle className="w-4 h-4" />
                  <span className="text-xs font-semibold uppercase tracking-wider">Final Fusion Score</span>
                </div>
                <p className={`text-4xl font-black font-mono z-10 ${
                  result.risk_assessment.risk_level === 'HIGH' ? 'text-red-500' : 
                  result.risk_assessment.risk_level === 'MEDIUM' ? 'text-yellow-400' : 'text-emerald-400'
                }`}>
                  {result.risk_assessment.risk_score}
                </p>
              </div>
            </div>

            {/* Alert Box */}
            <div className={`p-6 rounded-2xl border-2 flex items-start gap-5 ${
              result.risk_assessment.risk_level === 'HIGH' ? 'bg-red-950/40 border-red-900/80 text-red-100 shadow-[0_0_30px_-5px_rgba(220,38,38,0.3)]' :
              result.risk_assessment.risk_level === 'MEDIUM' ? 'bg-yellow-950/40 border-yellow-900/80 text-yellow-100' :
              'bg-emerald-950/40 border-emerald-900/80 text-emerald-100'
            }`}>
              {result.risk_assessment.risk_level === 'HIGH' ? <ShieldAlert className="w-10 h-10 text-red-500 shrink-0 mt-1" /> : 
               result.risk_assessment.risk_level === 'MEDIUM' ? <AlertTriangle className="w-10 h-10 text-yellow-500 shrink-0 mt-1" /> :
               <Shield className="w-10 h-10 text-emerald-500 shrink-0 mt-1" />}
              
              <div className="flex-1">
                <h3 className="text-2xl font-black mb-2 tracking-tight">
                  {result.risk_assessment.risk_level === 'HIGH' ? '🚨 HIGH IMPERSONATION RISK' : 
                   result.risk_assessment.risk_level === 'MEDIUM' ? '⚠️ VERIFICATION RECOMMENDED' : 
                   '✅ SECURE CONVERSATION'}
                </h3>
                <p className="opacity-90 mb-5 leading-relaxed text-lg">
                  {result.risk_assessment.risk_level === 'HIGH' ? 'Multiple signals indicate a severe threat. High synthetic probability combined with poor speaker verification and prosodic anomalies.' :
                   result.risk_assessment.risk_level === 'MEDIUM' ? 'Some indicators present conflicting signals. Speaker match may be low or prosody exhibits unnatural patterns.' :
                   'All signals (Authenticity, Identity, and Prosody) align with genuine human speech patterns.'}
                </p>
                
                <div className="flex items-center justify-between bg-black/30 p-4 rounded-xl">
                  <div className="flex flex-col">
                    <span className="text-xs uppercase tracking-wider opacity-70 font-semibold mb-1">System Action Triggered</span>
                    <span className="font-bold text-lg tracking-wide">
                      {result.risk_assessment.recommended_action.replace(/_/g, ' ')}
                    </span>
                  </div>
                </div>
              </div>
            </div>

          </div>
        )}
      </main>
    </div>
  );
}