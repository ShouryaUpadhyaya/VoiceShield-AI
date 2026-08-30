"use client";

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { MlApi } from '@/lib/mlApi';
import { useMlLabStore } from '@/stores/ml-lab-store';
import { AudioUpload } from '@/components/ui/AudioUpload';
import { Activity, AlertCircle, ChevronRight, FileJson } from 'lucide-react';
import Link from 'next/link';

const MODEL_INFO: Record<string, { key: string, name: string, type: string }> = {
  'indic': { key: 'indic', name: 'Indic Detector', type: 'Synthetic Speech Detection' },
  'dhwani': { key: 'dhwani', name: 'Dhwani', type: 'Deepfake Detection' },
  'custom-deepfake': { key: 'customDeepfake', name: 'Custom Deepfake', type: 'Deepfake Detection' },
  'prosody': { key: 'prosody', name: 'Prosody Analyzer', type: 'Rhythm & Pitch Analysis' },
  'speaker': { key: 'speaker', name: 'Speaker Verification', type: 'Identity Verification' }
};

export default function SingleModelPage() {
  const params = useParams();
  const routeModelName = params.modelName as string;
  const info = MODEL_INFO[routeModelName];

  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedJson, setExpandedJson] = useState(false);

  const { modelsStatus, setModelsStatus } = useMlLabStore();

  useEffect(() => {
    MlApi.getModels().then(data => {
      if (data.models) setModelsStatus(data.models);
    }).catch(console.error);
  }, [setModelsStatus]);

  if (!info) {
    return <div className="p-8 text-rose-400">Model not found.</div>;
  }

  const status = modelsStatus[info.key];
  const isReady = status?.status === 'ready';

  const runModel = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const data = await MlApi.runModel(info.key, file);
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'An error occurred during inference.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto w-full">
      <div className="flex items-center gap-2 text-sm text-slate-500 mb-6">
        <Link href="/models" className="hover:text-slate-300 transition-colors">ML Model Lab</Link>
        <ChevronRight className="w-4 h-4" />
        <span className="text-slate-300">{info.name}</span>
      </div>

      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="flex items-center gap-4 mb-2">
            <h1 className="text-3xl font-bold text-slate-100">{info.name}</h1>
            {status && (
              <span className={`px-2 py-1 rounded text-xs font-bold uppercase tracking-wider ${
                isReady ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
              }`}>
                {status.status}
              </span>
            )}
          </div>
          <p className="text-slate-400">{info.type}</p>
        </div>
      </div>

      {!isReady && status && (
        <div className="mb-8 p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-start gap-3 text-rose-400">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <h4 className="font-semibold mb-1">Model Unavailable</h4>
            <p className="text-sm opacity-90">{status.reason || 'This model cannot be tested at the moment.'}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
            <h2 className="text-lg font-bold text-slate-100 mb-4">TEST AUDIO</h2>
            <AudioUpload onFileSelect={setFile} disabled={!isReady || loading} />
            
            <button
              onClick={runModel}
              disabled={!file || !isReady || loading}
              className={`mt-6 w-full py-3 rounded-xl font-bold flex items-center justify-center gap-2 transition-all ${
                !file || !isReady || loading 
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed' 
                  : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 hover:shadow-[0_0_20px_rgba(16,185,129,0.3)]'
              }`}
            >
              {loading ? <><Activity className="w-5 h-5 animate-spin" /> Processing...</> : 'Run Model'}
            </button>
          </div>
          
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">Model Information</h2>
            <div className="space-y-3 text-sm text-slate-300">
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-500">Version</span>
                <span className="font-mono">{status?.version || '—'}</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-500">Supported Formats</span>
                <span>WAV, MP3, FLAC, M4A, OGG</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Sample Rate</span>
                <span>16 kHz</span>
              </div>
            </div>
          </div>
        </div>

        <div>
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 h-full flex flex-col">
            <h2 className="text-lg font-bold text-slate-100 mb-4">RESULT</h2>
            
            {error && (
              <div className="p-4 bg-rose-500/10 text-rose-400 border border-rose-500/20 rounded-xl text-sm">
                {error}
              </div>
            )}
            
            {!result && !error && !loading && (
              <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
                Upload a file and run the model to see results.
              </div>
            )}
            
            {loading && (
              <div className="flex-1 flex flex-col items-center justify-center text-emerald-500 space-y-4">
                <Activity className="w-8 h-8 animate-spin" />
                <span className="text-sm font-medium animate-pulse">Running inference...</span>
              </div>
            )}
            
            {result && !loading && (
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                    <p className="text-xs text-slate-500 uppercase font-semibold mb-1">Latency</p>
                    <p className="text-2xl font-bold text-slate-200">{result.latencyMs} <span className="text-sm font-normal text-slate-500">ms</span></p>
                  </div>
                  
                  {result.result?.synthetic_probability !== undefined && (
                    <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                      <p className="text-xs text-slate-500 uppercase font-semibold mb-1">Synthetic Score</p>
                      <p className={`text-2xl font-bold ${result.result.synthetic_probability > 0.5 ? 'text-amber-400' : 'text-emerald-400'}`}>
                        {(result.result.synthetic_probability * 100).toFixed(1)} <span className="text-sm font-normal text-slate-500">%</span>
                      </p>
                    </div>
                  )}
                  
                  {result.result?.deepfake_probability !== undefined && (
                    <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                      <p className="text-xs text-slate-500 uppercase font-semibold mb-1">Deepfake Score</p>
                      <p className={`text-2xl font-bold ${result.result.deepfake_probability > 0.5 ? 'text-amber-400' : 'text-emerald-400'}`}>
                        {(result.result.deepfake_probability * 100).toFixed(1)} <span className="text-sm font-normal text-slate-500">%</span>
                      </p>
                    </div>
                  )}

                  {result.result?.overall_prosody_risk !== undefined && (
                    <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                      <p className="text-xs text-slate-500 uppercase font-semibold mb-1">Anomaly Score</p>
                      <p className={`text-2xl font-bold ${result.result.overall_prosody_risk > 0.5 ? 'text-amber-400' : 'text-emerald-400'}`}>
                        {(result.result.overall_prosody_risk * 100).toFixed(1)} <span className="text-sm font-normal text-slate-500">%</span>
                      </p>
                    </div>
                  )}
                </div>

                <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950">
                  <button 
                    onClick={() => setExpandedJson(!expandedJson)}
                    className="w-full flex items-center justify-between p-3 bg-slate-900 text-sm font-medium hover:bg-slate-800 transition-colors"
                  >
                    <span className="flex items-center gap-2"><FileJson className="w-4 h-4" /> Raw Output</span>
                    <span className="text-slate-500 text-xs">{expandedJson ? 'Collapse' : 'Expand'}</span>
                  </button>
                  {expandedJson && (
                    <div className="p-4 overflow-x-auto max-h-[300px] overflow-y-auto">
                      <pre className="text-xs text-emerald-400/90 font-mono">
                        {JSON.stringify(result.result, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
