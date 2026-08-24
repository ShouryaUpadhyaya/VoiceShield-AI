import React, { useState } from 'react';
import { CallSecurityState } from '../../types/security';
import { ChevronDown, ChevronUp, Activity, Fingerprint, Radio, Cpu, Clock, Zap } from 'lucide-react';

interface TechnicalSignalsProps {
  state: CallSecurityState;
}

export function TechnicalSignals({ state }: TechnicalSignalsProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-xl overflow-hidden">
      <button 
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-800/50 transition-colors"
      >
        <span className="font-semibold text-slate-300 flex items-center gap-2">
          <Cpu className="w-5 h-5 text-indigo-400" />
          Technical Signals
        </span>
        {expanded ? <ChevronUp className="w-5 h-5 text-slate-500" /> : <ChevronDown className="w-5 h-5 text-slate-500" />}
      </button>

      {expanded && (
        <div className="p-6 pt-0 space-y-4 animate-in slide-in-from-top-2 duration-300">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
              <div className="flex justify-between items-center mb-1">
                <span className="text-sm font-semibold text-slate-400 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-cyan-400" />
                  Synthetic Probability
                </span>
                <span className="font-mono text-cyan-400 font-bold">
                  {state.spoofProbability !== undefined ? `${(state.spoofProbability * 100).toFixed(1)}%` : '--'}
                </span>
              </div>
              <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2">
                <div 
                  className="bg-cyan-500 h-1.5 rounded-full" 
                  style={{ width: `${(state.spoofProbability || 0) * 100}%` }}
                />
              </div>
            </div>

            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
              <div className="flex justify-between items-center mb-1">
                <span className="text-sm font-semibold text-slate-400 flex items-center gap-2">
                  <Fingerprint className="w-4 h-4 text-purple-400" />
                  Speaker Similarity
                </span>
                <span className="font-mono text-purple-400 font-bold">
                  {state.speakerSimilarity !== undefined ? `${(state.speakerSimilarity * 100).toFixed(1)}%` : '--'}
                </span>
              </div>
              <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2">
                <div 
                  className="bg-purple-500 h-1.5 rounded-full" 
                  style={{ width: `${(state.speakerSimilarity || 0) * 100}%` }}
                />
              </div>
            </div>

            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
              <div className="flex justify-between items-center mb-1">
                <span className="text-sm font-semibold text-slate-400 flex items-center gap-2">
                  <Radio className="w-4 h-4 text-pink-400" />
                  Prosody Anomaly
                </span>
                <span className="font-mono text-pink-400 font-bold">
                  {state.prosodyAnomaly !== undefined ? (state.prosodyAnomaly > 0.7 ? 'HIGH' : state.prosodyAnomaly > 0.4 ? 'MEDIUM' : 'LOW') : '--'}
                </span>
              </div>
              <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2">
                <div 
                  className={`h-1.5 rounded-full ${state.prosodyAnomaly && state.prosodyAnomaly > 0.7 ? 'bg-red-500' : 'bg-pink-500'}`} 
                  style={{ width: `${(state.prosodyAnomaly || 0) * 100}%` }}
                />
              </div>
            </div>
            
            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
              <div className="flex justify-between items-center h-full">
                 <div className="flex flex-col gap-2 w-full">
                    <span className="text-xs text-slate-500 flex items-center gap-1"><Zap className="w-3 h-3" /> Model: AudioSpectra v2.1</span>
                    <span className="text-xs text-slate-500 flex items-center gap-1"><Clock className="w-3 h-3" /> Window: 2.5s Rolling</span>
                 </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
