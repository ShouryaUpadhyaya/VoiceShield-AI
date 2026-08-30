"use client";

import { useState } from 'react';
import { MlApi } from '@/lib/mlApi';
import { AudioUpload } from './AudioUpload';
import { Activity, AlertTriangle, FileJson, CheckCircle } from 'lucide-react';

export function PipelineTest() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedJson, setExpandedJson] = useState(false);

  const runPipeline = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const data = await MlApi.runPipeline(file);
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Pipeline failed to execute.');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status?: string) => {
    if (status === 'complete') return 'text-emerald-400';
    if (status === 'unavailable') return 'text-amber-400';
    return 'text-slate-500';
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 mb-8">
      <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wide mb-6">Test With Audio File</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div>
          <AudioUpload onFileSelect={setFile} disabled={loading} />
          <button
            onClick={runPipeline}
            disabled={!file || loading}
            className={`mt-6 w-full py-3 rounded-xl font-bold flex items-center justify-center gap-2 transition-all ${
              !file || loading 
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed' 
                : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 hover:shadow-[0_0_20px_rgba(16,185,129,0.3)]'
            }`}
          >
            {loading ? <><Activity className="w-5 h-5 animate-spin" /> Processing Pipeline...</> : 'Run Full Pipeline'}
          </button>
        </div>

        <div>
          {error && (
            <div className="p-4 bg-rose-500/10 text-rose-400 border border-rose-500/20 rounded-xl text-sm mb-4">
              {error}
            </div>
          )}
          
          {loading && (
            <div className="h-full flex flex-col items-center justify-center text-emerald-500 space-y-4 py-12 border border-slate-800 rounded-xl bg-slate-950/50">
              <Activity className="w-8 h-8 animate-spin" />
              <div className="text-sm font-medium animate-pulse text-center">
                <p>Uploading...</p>
                <p className="text-xs text-slate-500 mt-2">Running Detectors & Fusion</p>
              </div>
            </div>
          )}

          {result && !loading && (
            <div className="border border-slate-800 rounded-xl bg-slate-950 overflow-hidden">
              <div className="p-6 border-b border-slate-800 flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">AI-Generated Score</h3>
                  <div className={`text-4xl font-black ${
                    (result.result?.fusion?.aiGeneratedScore || 0) > 0.5 ? 'text-amber-400' : 'text-emerald-400'
                  }`}>
                    {result.result?.fusion?.aiGeneratedScore !== undefined ? (result.result.fusion.aiGeneratedScore * 100).toFixed(1) : '--'}<span className="text-lg font-normal text-slate-500 ml-1">%</span>
                  </div>
                </div>
                <div className="text-right">
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Total Latency</h3>
                  <div className="text-xl font-bold text-slate-200">{result.latencyMs}<span className="text-sm font-normal text-slate-500 ml-1">ms</span></div>
                </div>
              </div>

              <div className="p-6 bg-slate-900/50">
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">Score Breakdown</h4>
                <div className="space-y-4">
                  {['indic', 'dhwani', 'customDeepfake', 'prosody'].map(key => {
                    const detector = result.result?.detectors?.[key];
                    const contrib = result.result?.fusion?.contributions?.[key];
                    const meta = result.result?.models_available?.[key] === false ? 'Unavailable' : 'Complete';
                    const score = detector?.score !== undefined ? (detector.score * 100).toFixed(1) + '%' : '—';
                    const weight = detector?.weight !== undefined ? (detector.weight * 100).toFixed(0) + '%' : '—';
                    const cont = contrib !== undefined ? (contrib * 100).toFixed(2) + '%' : '—';
                    
                    return (
                      <div key={key} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-lg border border-slate-800 bg-slate-950">
                        <div className="flex items-center gap-2 min-w-[140px]">
                          {meta === 'Complete' ? <CheckCircle className="w-4 h-4 text-emerald-500" /> : <AlertTriangle className="w-4 h-4 text-amber-500" />}
                          <span className="text-sm font-bold text-slate-200 capitalize">{key.replace(/([A-Z])/g, ' $1').trim()}</span>
                        </div>
                        <div className="flex items-center gap-6 text-sm text-slate-400 font-mono">
                          <div className="flex flex-col items-end"><span className="text-[10px] uppercase text-slate-600">Score</span><span className={detector?.status === 'complete' ? 'text-slate-300' : ''}>{score}</span></div>
                          <div className="flex flex-col items-end"><span className="text-[10px] uppercase text-slate-600">Weight</span><span>{weight}</span></div>
                          <div className="flex flex-col items-end"><span className="text-[10px] uppercase text-slate-600">Contrib</span><span className="text-indigo-400">{cont}</span></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <button 
                onClick={() => setExpandedJson(!expandedJson)}
                className="w-full flex items-center justify-between p-4 bg-slate-900 text-sm font-medium hover:bg-slate-800 transition-colors border-t border-slate-800"
              >
                <span className="flex items-center gap-2"><FileJson className="w-4 h-4" /> View Raw Result</span>
                <span className="text-slate-500 text-xs">{expandedJson ? 'Collapse' : 'Expand'}</span>
              </button>
              {expandedJson && (
                <div className="p-4 overflow-x-auto max-h-[300px] overflow-y-auto bg-slate-950">
                  <pre className="text-xs text-emerald-400/90 font-mono">
                    {JSON.stringify(result.result, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}

          {!result && !loading && !error && (
            <div className="h-full flex items-center justify-center border border-dashed border-slate-700 rounded-xl text-slate-500 text-sm py-12">
              Result will appear here.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
