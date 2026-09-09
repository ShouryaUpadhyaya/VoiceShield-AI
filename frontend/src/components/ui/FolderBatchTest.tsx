'use client';

import { useEffect, useRef, useState } from 'react';
import { FolderOpen, Play, Square, Download, Pause } from 'lucide-react';
import { MlApi } from '@/lib/mlApi';

/**
 * Run one model over every audio file in a folder.
 *
 * Files are sent one at a time, deliberately. The detectors are CPU-bound and
 * share one process, so firing a folder's worth of uploads in parallel does not
 * make it finish sooner -- it just queues inside the service and can starve the
 * live gateway path. Serial keeps the UI responsive and the numbers honest.
 *
 * Nothing is uploaded until you press Run, and the browser only reads the files
 * you explicitly select.
 */

const AUDIO_RE = /\.(wav|mp3|flac|ogg|m4a|aac|opus)$/i;

type Row = {
  name: string;
  score: number | null;   // model's primary score, normalised to "higher = more synthetic"
  raw: unknown;
  ms: number | null;
  error?: string;
};

/** Each adapter names its score differently; map them to one number. */
function primaryScore(model: string, result: Record<string, unknown> | null): number | null {
  if (!result) return null;
  const pick = (k: string) => (typeof result[k] === 'number' ? (result[k] as number) : null);
  switch (model) {
    case 'indic':
    case 'dhwani':          return pick('synthetic_probability');
    case 'custom-deepfake': return pick('deepfake_probability');
    case 'prosody':         return pick('overall_prosody_risk') ?? pick('anomaly_score');
    default:                return pick('synthetic_probability') ?? pick('deepfake_probability');
  }
}

export function FolderBatchTest({ modelKey, modelName, disabled }:
  { modelKey: string; modelName: string; disabled?: boolean }) {
  const [files, setFiles] = useState<File[]>([]);
  const [rows, setRows] = useState<Row[]>([]);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(0);
  const [threshold, setThreshold] = useState(0.5);
  const abort = useRef(false);

  // Inline playback. The File objects are already in memory from the folder
  // picker, so a row can be auditioned without re-reading from disk or hitting
  // the network. One <audio> is reused and exactly one object URL is alive at a
  // time -- creating 500 of them up front would leak until the page unloaded.
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  const [playingName, setPlayingName] = useState<string | null>(null);

  const releaseUrl = () => {
    if (urlRef.current) { URL.revokeObjectURL(urlRef.current); urlRef.current = null; }
  };

  const togglePlay = (name: string) => {
    const a = audioRef.current;
    if (!a) return;
    if (playingName === name) {                    // same row -> pause/resume
      if (a.paused) { void a.play(); } else { a.pause(); setPlayingName(null); }
      return;
    }
    const f = files.find(x => x.name === name);
    if (!f) return;
    a.pause();
    releaseUrl();
    urlRef.current = URL.createObjectURL(f);
    a.src = urlRef.current;
    a.currentTime = 0;
    void a.play();
    setPlayingName(name);
  };

  useEffect(() => () => { releaseUrl(); }, []);

  const pickFolder = (list: FileList | null) => {
    if (!list) return;
    const audio = Array.from(list).filter(f => AUDIO_RE.test(f.name))
                       .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
    audioRef.current?.pause();
    releaseUrl();
    setPlayingName(null);
    setFiles(audio);
    setRows([]);
    setDone(0);
  };

  const run = async () => {
    setRunning(true); abort.current = false; setRows([]); setDone(0);
    const out: Row[] = [];
    for (const f of files) {
      if (abort.current) break;
      const t0 = performance.now();
      try {
        const data = await MlApi.runModel(modelKey, f);
        out.push({ name: f.name, score: primaryScore(modelKey, data?.result ?? null),
                   raw: data?.result ?? null, ms: Math.round(performance.now() - t0) });
      } catch (e) {
        out.push({ name: f.name, score: null, raw: null, ms: null,
                   error: e instanceof Error ? e.message : 'failed' });
      }
      setDone(out.length);
      setRows([...out]);          // stream results as they land
    }
    setRunning(false);
  };

  const scored = rows.filter(r => r.score != null) as (Row & { score: number })[];
  const flagged = scored.filter(r => r.score >= threshold).length;
  const mean = scored.length ? scored.reduce((a, r) => a + r.score, 0) / scored.length : null;
  const failed = rows.filter(r => r.error).length;

  const csv = () => {
    const body = ['file,score,latency_ms,error',
      ...rows.map(r => `"${r.name}",${r.score ?? ''},${r.ms ?? ''},"${r.error ?? ''}"`)].join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([body], { type: 'text/csv' }));
    a.download = `${modelKey}-batch.csv`; a.click(); URL.revokeObjectURL(a.href);
  };

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          <FolderOpen className="w-4 h-4" /> Batch test a folder — {modelName}
        </h3>
        {rows.length > 0 && (
          <button onClick={csv}
                  className="text-xs text-slate-400 hover:text-white flex items-center gap-1.5">
            <Download className="w-3.5 h-3.5" /> CSV
          </button>
        )}
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <label className={`text-xs px-4 py-2 rounded-lg border border-dashed cursor-pointer transition-colors
                          ${disabled ? 'border-slate-800 text-slate-600 cursor-not-allowed'
                                     : 'border-slate-700 text-slate-300 hover:border-indigo-500/60'}`}>
          {files.length ? `${files.length} audio files selected` : 'Choose a folder…'}
          <input type="file" className="hidden" multiple disabled={disabled}
                 // @ts-expect-error non-standard but supported in Chromium/WebKit/Firefox
                 webkitdirectory="" directory=""
                 onChange={e => pickFolder(e.target.files)} />
        </label>

        <button onClick={running ? () => { abort.current = true; } : run}
                disabled={disabled || !files.length}
                className={`text-xs px-4 py-2 rounded-lg flex items-center gap-2 transition-colors
                  ${!files.length || disabled ? 'bg-slate-800 text-slate-600 cursor-not-allowed'
                    : running ? 'bg-red-600 hover:bg-red-500 text-white'
                              : 'bg-indigo-600 hover:bg-indigo-500 text-white'}`}>
          {running ? <><Square className="w-3.5 h-3.5" /> Stop</> : <><Play className="w-3.5 h-3.5" /> Run all</>}
        </button>

        <label className="text-xs text-slate-500 flex items-center gap-2">
          flag at
          <input type="number" step="0.01" min="0" max="1" value={threshold}
                 onChange={e => setThreshold(Number(e.target.value))}
                 className="w-16 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono" />
        </label>
      </div>

      {(running || rows.length > 0) && (
        <div className="space-y-3">
          <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full bg-indigo-500 transition-all"
                 style={{ width: `${files.length ? (done / files.length) * 100 : 0}%` }} />
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
            <Stat label="scored" value={`${scored.length}/${files.length}`} />
            <Stat label={`≥ ${threshold}`} value={`${flagged}`}
                  tone={flagged ? 'text-red-400' : 'text-emerald-400'} />
            <Stat label="mean score" value={mean == null ? '—' : mean.toFixed(4)} />
            <Stat label="failed" value={`${failed}`} tone={failed ? 'text-amber-400' : undefined} />
          </div>

          <audio ref={audioRef}
                 onEnded={() => setPlayingName(null)}
                 onPause={() => { if (audioRef.current?.ended) setPlayingName(null); }} />

          {playingName && (
            <div className="text-[11px] text-indigo-300 font-mono truncate">
              ▶ {playingName}
            </div>
          )}

          <div className="max-h-80 overflow-y-auto rounded-lg border border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-900 text-slate-500">
                <tr><th className="w-8 px-2 py-2"></th>
                    <th className="text-left px-3 py-2">file</th>
                    <th className="text-right px-3 py-2">score</th>
                    <th className="text-right px-3 py-2">ms</th></tr>
              </thead>
              <tbody className="font-mono">
                {rows.map(r => (
                  <tr key={r.name}
                      className={`border-t border-slate-800/60 ${
                        playingName === r.name ? 'bg-indigo-950/50' : 'hover:bg-slate-800/30'}`}>
                    <td className="px-2 py-1.5">
                      <button onClick={() => togglePlay(r.name)}
                              title={playingName === r.name ? 'Pause' : `Play ${r.name}`}
                              className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
                                playingName === r.name
                                  ? 'bg-indigo-500 text-white'
                                  : 'bg-slate-800 text-slate-400 hover:bg-indigo-600 hover:text-white'}`}>
                        {playingName === r.name
                          ? <Pause className="w-3 h-3" />
                          : <Play className="w-3 h-3 ml-0.5" />}
                      </button>
                    </td>
                    <td className="px-3 py-1.5 text-slate-300 truncate max-w-[22rem]" title={r.name}>{r.name}</td>
                    <td className={`px-3 py-1.5 text-right ${
                      r.error ? 'text-amber-400'
                      : r.score == null ? 'text-slate-600'
                      : r.score >= threshold ? 'text-red-400' : 'text-emerald-400'}`}>
                      {r.error ? r.error.slice(0, 34) : r.score == null ? '—' : r.score.toFixed(4)}
                    </td>
                    <td className="px-3 py-1.5 text-right text-slate-600">{r.ms ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="bg-slate-800/50 rounded-lg py-2">
      <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`text-sm font-mono ${tone ?? 'text-slate-200'}`}>{value}</div>
    </div>
  );
}
