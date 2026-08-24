import React from 'react';
import { SecurityAlert as SecurityAlertType } from '../../types/security';
import { AlertOctagon, ShieldAlert, AlertTriangle } from 'lucide-react';

interface SecurityAlertProps {
  alert: SecurityAlertType | undefined;
  onVerify: () => void;
  onEscalate: () => void;
}

export function SecurityAlert({ alert, onVerify, onEscalate }: SecurityAlertProps) {
  if (!alert) return null;

  const isCritical = alert.severity === 'CRITICAL';
  
  return (
    <div className={`mt-6 p-6 rounded-2xl border-2 flex flex-col md:flex-row items-start md:items-center justify-between gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500 shadow-2xl ${
      isCritical ? 'bg-red-950/40 border-red-900/80 text-red-100 shadow-[0_0_30px_-5px_rgba(220,38,38,0.3)]' : 
      'bg-yellow-950/40 border-yellow-900/80 text-yellow-100'
    }`}>
      <div className="flex items-start gap-4">
        <div className={`p-3 rounded-xl shrink-0 ${isCritical ? 'bg-red-900/50' : 'bg-yellow-900/50'}`}>
          {isCritical ? <AlertOctagon className="w-8 h-8 text-red-400" /> : <AlertTriangle className="w-8 h-8 text-yellow-400" />}
        </div>
        <div>
          <h3 className="text-xl font-black tracking-tight flex items-center gap-2">
            {isCritical ? '🚨 CRITICAL SECURITY ALERT' : '⚠️ HIGH RISK WARNING'}
          </h3>
          <p className="opacity-90 mt-2 font-medium">
            {isCritical ? 'Possible AI-generated / manipulated voice detected.' : 'Significant anomalies detected in voice patterns.'}
          </p>
          <div className="mt-4 text-sm bg-black/20 p-3 rounded-lg border border-white/10">
            <p className="font-semibold mb-1">Recommended Action:</p>
            <ul className="list-disc list-inside opacity-90 space-y-1">
              {alert.recommended_action === 'SECONDARY_VERIFICATION' && (
                <>
                  <li>Verify caller through trusted channel</li>
                  <li>Require MFA</li>
                  {isCritical && <li>Do not approve sensitive transaction</li>}
                </>
              )}
              {alert.recommended_action === 'CONTINUE_MONITORING' && (
                <>
                  <li>Monitor call closely</li>
                  <li>Ask security questions if discussing sensitive topics</li>
                </>
              )}
            </ul>
          </div>
        </div>
      </div>
      
      <div className="flex flex-col sm:flex-row w-full md:w-auto gap-3 shrink-0">
        <button 
          onClick={onVerify}
          className={`px-6 py-3 rounded-xl font-bold transition-all shadow-lg flex items-center justify-center gap-2 ${
            isCritical ? 'bg-red-600 hover:bg-red-500 text-white' : 'bg-yellow-600 hover:bg-yellow-500 text-white'
          }`}
        >
          <ShieldAlert className="w-5 h-5" />
          VERIFY CALLER
        </button>
        <button 
          onClick={onEscalate}
          className="px-6 py-3 rounded-xl font-bold bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 transition-all flex items-center justify-center"
        >
          ESCALATE
        </button>
      </div>
    </div>
  );
}
