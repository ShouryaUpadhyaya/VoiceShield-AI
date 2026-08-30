"use client";

import { useState, useRef } from 'react';
import { UploadCloud, X, FileAudio } from 'lucide-react';

interface AudioUploadProps {
  onFileSelect: (file: File | null) => void;
  disabled?: boolean;
}

export function AudioUpload({ onFileSelect, disabled = false }: AudioUploadProps) {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const supportedTypes = ['audio/wav', 'audio/mpeg', 'audio/mp3', 'audio/flac', 'audio/ogg', 'audio/x-m4a'];

  const handleFile = (selectedFile: File) => {
    setError(null);
    if (!supportedTypes.includes(selectedFile.type) && !selectedFile.name.match(/\.(wav|mp3|flac|m4a|ogg)$/i)) {
      setError('Unsupported file format. Please upload WAV, MP3, FLAC, M4A, or OGG.');
      return;
    }
    const maxMb = 25;
    if (selectedFile.size > maxMb * 1024 * 1024) {
      setError(`File exceeds maximum allowed size of ${maxMb}MB.`);
      return;
    }
    if (selectedFile.size === 0) {
      setError('File is empty.');
      return;
    }
    setFile(selectedFile);
    onFileSelect(selectedFile);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (disabled) return;
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (disabled) return;
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const removeFile = () => {
    setFile(null);
    setError(null);
    onFileSelect(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div className="w-full">
      {!file ? (
        <div
          className={`relative border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center transition-colors ${
            disabled ? 'opacity-50 cursor-not-allowed border-slate-700 bg-slate-900/50' : 
            dragActive ? 'border-emerald-500 bg-emerald-500/10' : 'border-slate-700 hover:border-slate-500 bg-slate-900/50'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => !disabled && inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".wav,.mp3,.flac,.m4a,.ogg,audio/*"
            className="hidden"
            onChange={handleChange}
            disabled={disabled}
          />
          <UploadCloud className="w-10 h-10 text-slate-400 mb-4" />
          <p className="text-sm font-medium text-slate-200 mb-1">
            Drop audio file here or click to browse
          </p>
          <p className="text-xs text-slate-500">
            Supported: .wav, .mp3, .flac, .m4a, .ogg (Max 25MB)
          </p>
          {error && <p className="text-xs text-rose-500 mt-4">{error}</p>}
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 flex items-center gap-4">
          <div className="w-12 h-12 bg-emerald-500/10 rounded-lg flex items-center justify-center shrink-0">
            <FileAudio className="w-6 h-6 text-emerald-400" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-slate-200 truncate">{file.name}</p>
            <p className="text-xs text-slate-500">
              {(file.size / (1024 * 1024)).toFixed(2)} MB • {file.type || 'audio file'}
            </p>
            <audio 
              src={URL.createObjectURL(file)} 
              controls 
              className="mt-2 h-8 w-full max-w-md [&::-webkit-media-controls-panel]:bg-slate-800"
            />
          </div>
          <button
            onClick={removeFile}
            className="p-2 text-slate-400 hover:text-rose-400 transition-colors"
            disabled={disabled}
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      )}
    </div>
  );
}
