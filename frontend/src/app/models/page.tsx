"use client";

import { useEffect } from 'react';
import Link from 'next/link';
import { MlApi } from '@/lib/mlApi';
import { useMlLabStore } from '@/stores/ml-lab-store';
import { Activity, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';

const MODEL_META = {
  indic: { name: 'Indic Detector', desc: 'Synthetic speech detection tailored for Indic languages.', reqs: '16 kHz • WAV/MP3', path: '/models/indic' },
  dhwani: { name: 'Dhwani', desc: 'Deepfake detection model.', reqs: '16 kHz • WAV/MP3', path: '/models/dhwani' },
  customDeepfake: { name: 'Custom Deepfake', desc: 'P90-pooled deepfake sliding window detector.', reqs: '16 kHz • WAV/MP3', path: '/models/custom-deepfake' },
  prosody: { name: 'Prosody Analyzer', desc: 'Voice rhythm and pitch anomaly detection.', reqs: '16 kHz • WAV/MP3', path: '/models/prosody' },
  speaker: { name: 'Speaker Verification', desc: 'ECAPA-based speaker identity verification.', reqs: '16 kHz • WAV/MP3', path: '/models/speaker' },
};

export default function ModelsPage() {
  const { modelsStatus, setModelsStatus } = useMlLabStore();

  useEffect(() => {
    MlApi.getModels().then(data => {
      if (data.models) {
        setModelsStatus(data.models);
      }
    }).catch(console.error);
  }, [setModelsStatus]);

  const getStatusIcon = (status: string) => {
    switch(status) {
      case 'ready': return <CheckCircle className="w-4 h-4 text-emerald-400" />;
      case 'loading': return <Activity className="w-4 h-4 text-amber-400 animate-pulse" />;
      case 'error': return <AlertTriangle className="w-4 h-4 text-rose-400" />;
      default: return <XCircle className="w-4 h-4 text-slate-500" />;
    }
  };

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-100 mb-2">ML Model Lab</h1>
          <p className="text-slate-400">Test and evaluate individual deepfake and voice analysis models.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {Object.entries(MODEL_META).map(([key, meta]) => {
          const status = modelsStatus[key];
          const isReady = status?.status === 'ready';

          return (
            <div key={key} className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden flex flex-col">
              <div className="p-6 flex-1">
                <div className="flex items-start justify-between mb-4">
                  <h3 className="text-lg font-bold text-slate-100 uppercase tracking-wide">{meta.name}</h3>
                  <div className="flex items-center gap-2 px-3 py-1 bg-slate-950 rounded-full border border-slate-800">
                    {getStatusIcon(status?.status || 'unavailable')}
                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                      {status?.status || 'UNKNOWN'}
                    </span>
                  </div>
                </div>
                
                <p className="text-sm text-slate-400 mb-6 min-h-[40px]">
                  {meta.desc}
                </p>

                <div className="space-y-2 text-xs font-mono text-slate-500 mb-6 bg-slate-950 p-4 rounded-xl">
                  <div className="flex justify-between">
                    <span>Input:</span>
                    <span className="text-slate-300">{meta.reqs}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Version:</span>
                    <span className="text-slate-300 truncate max-w-[120px]">{status?.version || '—'}</span>
                  </div>
                  {!isReady && status?.reason && (
                    <div className="mt-2 pt-2 border-t border-slate-800 text-amber-500/90 whitespace-normal">
                      Reason: {status.reason}
                    </div>
                  )}
                </div>
              </div>

              <div className="p-4 bg-slate-950 border-t border-slate-800">
                {isReady ? (
                  <Link 
                    href={meta.path}
                    className="flex items-center justify-center w-full py-2.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 font-medium rounded-lg transition-colors"
                  >
                    Test Model
                  </Link>
                ) : (
                  <button 
                    disabled
                    className="flex items-center justify-center w-full py-2.5 bg-slate-800/50 text-slate-500 font-medium rounded-lg cursor-not-allowed"
                  >
                    Unavailable
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
