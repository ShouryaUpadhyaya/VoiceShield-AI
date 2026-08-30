"use client";

import { useState } from 'react';
import { Smartphone, Activity, Terminal, Folder, Zap, FastForward, Info, XCircle } from 'lucide-react';

export function SimulatorTest() {
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState<string | null>(null);
  
  const [targetPath, setTargetPath] = useState('');
  const [concurrency, setConcurrency] = useState(1);
  const [speed, setSpeed] = useState(2.0);
  const [showInfo, setShowInfo] = useState(false);

  const stopSimulator = async () => {
    try {
      await fetch('/api/simulator/stop', { method: 'POST' });
      setOutput((prev) => (prev || '') + "\n[INFO] Sent stop signal to simulator.");
      setRunning(false);
    } catch (err: any) {
      setOutput((prev) => (prev || '') + "\n[ERROR] Failed to stop simulator: " + err.message);
    }
  };

  const runSimulator = async () => {
    setRunning(true);
    setOutput(`Starting Android simulator test...\nPath: ${targetPath || 'Default (trumpet)'}\nConcurrency: ${concurrency}\nSpeed: ${speed}x\n\n`);
    
    try {
      const res = await fetch('/api/simulator', { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: targetPath, concurrency, speed })
      });
      const data = await res.json();
      
      if (data.output) {
        setOutput((prev) => (prev || '') + data.output);
      }
      if (data.error) {
        setOutput((prev) => (prev || '') + "\n[ERROR]\n" + data.error);
      }
      if (!data.success) {
        setOutput((prev) => (prev || '') + "\nTest execution failed or was interrupted.");
      } else {
        setOutput((prev) => (prev || '') + "\nTest execution completed successfully.");
      }
    } catch (err: any) {
      setOutput((prev) => (prev || '') + "\nFailed to run simulator: " + err.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 mb-8 relative">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wide flex items-center gap-2">
            <Smartphone className="w-5 h-5" /> Android Simulator Test
          </h2>
          <button 
            onClick={() => setShowInfo(!showInfo)}
            className="text-slate-400 hover:text-slate-200 transition-colors"
          >
            <Info className="w-4 h-4" />
          </button>
        </div>
        
        <div className="flex items-center gap-2">
          {running && (
            <button
              onClick={stopSimulator}
              className="px-4 py-2 rounded-lg font-bold flex items-center gap-2 transition-colors bg-red-600/20 hover:bg-red-600/40 text-red-400"
            >
              <XCircle className="w-4 h-4" /> Stop
            </button>
          )}
          <button
            onClick={runSimulator}
            disabled={running}
            className={`px-4 py-2 rounded-lg font-bold flex items-center gap-2 transition-colors ${
              running 
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed' 
                : 'bg-indigo-600 hover:bg-indigo-500 text-white'
            }`}
          >
            {running ? <><Activity className="w-4 h-4 animate-spin" /> Running...</> : 'Run Simulator'}
          </button>
        </div>
      </div>
      
      {showInfo && (
        <div className="bg-indigo-900/20 border border-indigo-500/30 rounded-xl p-4 mb-6 text-sm text-indigo-200">
          <p className="mb-2"><strong>What this does:</strong></p>
          <ul className="list-disc pl-5 space-y-1">
            <li>Executes the <code>test_android_simulator.py</code> script locally to simulate an Android app dialing into the Gateway.</li>
            <li>Connects via WebSockets to the Node.js Media Gateway running on <code>ws://localhost:8010</code>.</li>
            <li>Streams audio data chunk-by-chunk in real-time (or accelerated) exactly like the real app.</li>
            <li>Triggers the complete VoiceShield-AI ML pipeline dynamically.</li>
          </ul>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-3">
          <label className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            <Folder className="w-3 h-3" /> Target Path / Directory
          </label>
          <input 
            type="text" 
            value={targetPath}
            onChange={(e) => setTargetPath(e.target.value)}
            placeholder="Leave empty for default"
            className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        <div className="bg-slate-950 border border-slate-800 rounded-xl p-3">
          <label className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            <Zap className="w-3 h-3" /> Concurrency
          </label>
          <input 
            type="number" 
            min="1" max="50"
            value={concurrency}
            onChange={(e) => setConcurrency(parseInt(e.target.value) || 1)}
            className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        <div className="bg-slate-950 border border-slate-800 rounded-xl p-3">
          <label className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            <FastForward className="w-3 h-3" /> Streaming Speed
          </label>
          <div className="flex items-center gap-2">
            <input 
              type="range" 
              min="0" max="10" step="0.5"
              value={speed}
              onChange={(e) => setSpeed(parseFloat(e.target.value))}
              className="flex-1 accent-indigo-500"
            />
            <span className="text-slate-300 text-sm font-mono w-10 text-right">{speed}x</span>
          </div>
        </div>
      </div>

      {output && (
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 overflow-hidden mt-4">
          <div className="flex items-center gap-2 text-slate-500 mb-2 text-xs font-semibold uppercase tracking-wider">
            <Terminal className="w-4 h-4" /> Simulator Output
          </div>
          <pre className="text-xs font-mono text-emerald-400/90 whitespace-pre-wrap max-h-[300px] overflow-y-auto">
            {output}
          </pre>
        </div>
      )}
    </div>
  );
}
