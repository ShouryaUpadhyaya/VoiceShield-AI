import React, { useEffect, useState } from 'react';

interface LiveWaveformProps {
  isActive: boolean;
  riskScore: number;
}

export function LiveWaveform({ isActive, riskScore }: LiveWaveformProps) {
  const [bars, setBars] = useState<number[]>(Array(40).fill(10));

  useEffect(() => {
    if (!isActive) {
      setBars(Array(40).fill(5));
      return;
    }

    const interval = setInterval(() => {
      setBars(prev => {
        const newBars = [...prev.slice(1)];
        // Generate a random height based on "activity" and slightly influenced by risk
        const baseActivity = Math.random() * 40 + 10;
        const volatility = (riskScore / 100) * 30; // Higher risk = more volatile waveform
        newBars.push(baseActivity + Math.random() * volatility);
        return newBars;
      });
    }, 100);

    return () => clearInterval(interval);
  }, [isActive, riskScore]);

  const getColorClass = () => {
    if (riskScore >= 76) return 'bg-red-500';
    if (riskScore >= 61) return 'bg-orange-500';
    if (riskScore >= 31) return 'bg-yellow-400';
    return 'bg-emerald-400';
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl h-48 flex flex-col justify-between">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-slate-400 font-semibold text-sm tracking-wider uppercase flex items-center gap-2">
          Live Audio Analysis
          {isActive && (
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
            </span>
          )}
        </h3>
        <span className="text-xs font-mono text-slate-500">8kHz / 16-bit / Mono</span>
      </div>
      
      <div className="flex-1 flex items-end justify-between gap-[2px] overflow-hidden">
        {bars.map((height, i) => (
          <div
            key={i}
            className={`w-full rounded-t-sm transition-all duration-100 ease-linear ${getColorClass()}`}
            style={{ height: `${Math.min(100, Math.max(5, height))}%`, opacity: (i / bars.length) * 0.8 + 0.2 }}
          />
        ))}
      </div>
    </div>
  );
}
