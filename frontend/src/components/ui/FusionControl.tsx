"use client";

import { useEffect, useState } from 'react';
import { MlApi } from '@/lib/mlApi';
import { useMlLabStore } from '@/stores/ml-lab-store';

export function FusionControl() {
  const { fusionWeights, previewWeights, setFusionWeights, setPreviewWeights, resetPreviewWeights, normalizePreviewWeights } = useMlLabStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    MlApi.getFusionConfig().then(data => {
      if (data.weights) {
        setFusionWeights(data.weights);
      }
    }).catch(console.error);
  }, [setFusionWeights]);
  
  const totalWeight = Object.values(previewWeights).reduce((a, b) => a + b, 0);
  const isValid = Math.abs(totalWeight - 1.0) < 0.01;
  const isChanged = JSON.stringify(fusionWeights) !== JSON.stringify(previewWeights);

  const applyChanges = async () => {
    if (!isValid) return;
    setLoading(true);
    setError(null);
    try {
      const data = await MlApi.updateFusionConfig(previewWeights);
      if (data.success) {
        setFusionWeights(data.weights);
      }
    } catch (e: any) {
      setError(e.message || 'Failed to update weights');
    } finally {
      setLoading(false);
    }
  };

  const handleSlider = (key: keyof typeof previewWeights, value: number) => {
    setPreviewWeights({ ...previewWeights, [key]: value / 100 });
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 mb-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wide">Model Fusion</h2>
        <div className={`text-sm font-medium px-3 py-1 rounded-full ${isValid ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
          Total: {(totalWeight * 100).toFixed(0)}%
        </div>
      </div>
      
      {error && <div className="mb-4 text-xs text-rose-400">{error}</div>}

      <div className="space-y-4">
        {Object.entries(previewWeights).map(([key, value]) => {
          const val100 = Math.round(value * 100);
          return (
            <div key={key} className="flex items-center gap-4">
              <div className="w-32 text-sm font-medium text-slate-300 capitalize">{key.replace(/([A-Z])/g, ' $1').trim()}</div>
              <input 
                type="range" 
                min="0" max="100" 
                value={val100}
                onChange={(e) => handleSlider(key as any, parseInt(e.target.value))}
                className="flex-1 accent-emerald-500"
              />
              <input 
                type="number"
                min="0" max="100"
                value={val100}
                onChange={(e) => handleSlider(key as any, parseInt(e.target.value))}
                className="w-16 bg-slate-950 border border-slate-800 rounded px-2 py-1 text-sm text-center text-slate-200"
              />
              <span className="text-slate-500 text-sm w-4">%</span>
            </div>
          );
        })}
      </div>

      <div className="mt-6 pt-4 border-t border-slate-800 flex items-center justify-between">
        <div className="flex gap-2">
          <button 
            onClick={normalizePreviewWeights}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium transition-colors"
          >
            Normalize
          </button>
          {isChanged && (
            <button 
              onClick={resetPreviewWeights}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium transition-colors"
            >
              Reset
            </button>
          )}
        </div>
        <button
          onClick={applyChanges}
          disabled={!isValid || !isChanged || loading}
          className={`px-6 py-2 rounded-lg text-sm font-bold transition-colors ${
            !isValid || !isChanged || loading 
              ? 'bg-slate-800 text-slate-500 cursor-not-allowed' 
              : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950'
          }`}
        >
          {loading ? 'Applying...' : 'Apply Weights'}
        </button>
      </div>
    </div>
  );
}
