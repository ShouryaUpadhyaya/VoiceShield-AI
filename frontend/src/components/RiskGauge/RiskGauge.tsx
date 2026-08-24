import React from 'react';
import { RiskLevel } from '../../types/security';
import { Shield, ShieldAlert, ShieldCheck, AlertTriangle } from 'lucide-react';

interface RiskGaugeProps {
  score: number;
  level: RiskLevel;
}

export function RiskGauge({ score, level }: RiskGaugeProps) {
  // Calculate stroke dasharray for the circular progress (circumference is ~283 for r=45)
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  const getColorClass = () => {
    switch (level) {
      case 'CRITICAL': return 'text-red-500';
      case 'HIGH': return 'text-orange-500';
      case 'MEDIUM': return 'text-yellow-400';
      case 'LOW':
      default: return 'text-emerald-400';
    }
  };

  const getStrokeClass = () => {
    switch (level) {
      case 'CRITICAL': return 'stroke-red-500';
      case 'HIGH': return 'stroke-orange-500';
      case 'MEDIUM': return 'stroke-yellow-400';
      case 'LOW':
      default: return 'stroke-emerald-400';
    }
  };

  const getIcon = () => {
    switch (level) {
      case 'CRITICAL': return <ShieldAlert className={`w-8 h-8 ${getColorClass()}`} />;
      case 'HIGH': return <ShieldAlert className={`w-8 h-8 ${getColorClass()}`} />;
      case 'MEDIUM': return <AlertTriangle className={`w-8 h-8 ${getColorClass()}`} />;
      case 'LOW':
      default: return <ShieldCheck className={`w-8 h-8 ${getColorClass()}`} />;
    }
  };

  return (
    <div className="relative flex flex-col items-center justify-center p-6 bg-slate-900 rounded-2xl border border-slate-800 shadow-xl">
      <h3 className="text-slate-400 font-semibold mb-4 text-sm tracking-wider uppercase">Impersonation Risk</h3>
      <div className="relative w-48 h-48 flex items-center justify-center">
        {/* Background track */}
        <svg className="absolute inset-0 w-full h-full transform -rotate-90">
          <circle
            cx="96"
            cy="96"
            r={radius}
            className="stroke-slate-800 fill-none"
            strokeWidth="12"
          />
          {/* Progress track */}
          <circle
            cx="96"
            cy="96"
            r={radius}
            className={`${getStrokeClass()} fill-none transition-all duration-700 ease-out`}
            strokeWidth="12"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
          />
        </svg>
        <div className="flex flex-col items-center z-10">
          <span className={`text-5xl font-black ${getColorClass()}`}>{score}</span>
          <span className="text-slate-500 text-sm mt-1">/ 100</span>
        </div>
      </div>
      <div className="mt-4 flex flex-col items-center gap-2">
        {getIcon()}
        <span className={`font-bold tracking-widest text-lg ${getColorClass()}`}>{level}</span>
      </div>
    </div>
  );
}
