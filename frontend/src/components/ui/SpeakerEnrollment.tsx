"use client";

import { useState } from 'react';
import { AudioUpload } from './AudioUpload';
import { FolderSearch, UserCheck, Loader2 } from 'lucide-react';

export function SpeakerEnrollment() {
  const [speakerId, setSpeakerId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [directoryPath, setDirectoryPath] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleEnrollSingle = async () => {
    if (!speakerId || !file) return;
    setLoading(true);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append('speaker_id', speakerId);
      formData.append('audio', file);
      
      const res = await fetch('http://localhost:8011/api/speaker/enroll', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'API Error');
      setResult(data);
    } catch (e: any) {
      setResult({ error: e.message || 'Failed to enroll' });
    } finally {
      setLoading(false);
    }
  };

  const handleEnrollDirectory = async () => {
    if (!directoryPath) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch('http://localhost:8011/api/speaker/enroll-directory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ directory_path: directoryPath }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'API Error');
      setResult(data);
    } catch (e: any) {
      setResult({ error: e.message || 'Failed to scan directory' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
      <h2 className="text-lg font-bold flex items-center gap-2 mb-6">
        <UserCheck className="w-5 h-5 text-indigo-400" />
        Speaker Enrollment (ECAPA-TDNN)
      </h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Single File Enrollment */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-slate-300 border-b border-slate-800 pb-2">Single User Enrollment</h3>
          
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Speaker ID / Name</label>
            <input 
              type="text" 
              value={speakerId}
              onChange={(e) => setSpeakerId(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              placeholder="e.g., john_doe"
            />
          </div>
          
          <AudioUpload onFileSelect={setFile} disabled={loading} />
          
          <button 
            onClick={handleEnrollSingle}
            disabled={!speakerId || !file || loading}
            className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white py-2 px-4 rounded-lg font-medium transition-colors"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserCheck className="w-4 h-4" />}
            Enroll Speaker
          </button>
        </div>

        {/* Directory Enrollment */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-slate-300 border-b border-slate-800 pb-2">Bulk Directory Enrollment</h3>
          <p className="text-xs text-slate-500 mb-2">Scan a local absolute folder path. Enrolls all .wav files using the filename as the speaker ID.</p>
          
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Absolute Directory Path</label>
            <div className="flex gap-2">
              <input 
                type="text" 
                value={directoryPath}
                onChange={(e) => setDirectoryPath(e.target.value)}
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
                placeholder="/home/shouryaupadhyaya/data/..."
              />
            </div>
          </div>
          
          <button 
            onClick={handleEnrollDirectory}
            disabled={!directoryPath || loading}
            className="w-full flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 disabled:opacity-50 disabled:cursor-not-allowed text-white py-2 px-4 rounded-lg font-medium transition-colors mt-2"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FolderSearch className="w-4 h-4" />}
            Scan & Enroll Directory
          </button>

          {/* Results Area */}
          {result && (
            <div className={`mt-4 p-4 rounded-lg border text-xs overflow-auto max-h-40 font-mono ${result.error ? 'bg-red-950/40 border-red-900/50 text-red-400' : 'bg-slate-950/50 border-slate-800 text-slate-300'}`}>
              <pre>{JSON.stringify(result, null, 2)}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
