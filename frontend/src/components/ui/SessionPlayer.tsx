'use client';

import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import { Play, Pause, Upload, X } from 'lucide-react';

/**
 * Plays a locally-chosen audio file alongside a session's chunk timeline.
 *
 * The gateway runs with debugAudio=false, so it keeps no playable copy of the
 * stream. Rather than change the gateway, the operator points this at the same
 * file that was streamed; the browser decodes it locally and never uploads it.
 *
 * Chunk k covers [k*chunkMs, (k+1)*chunkMs). We derive chunkMs from the chunks
 * themselves rather than assuming 3 s, because the gateway's chunk duration is
 * configurable and the last chunk of a call is usually short.
 */
export interface PlayerChunk {
  sequence: number;
  durationMs?: number;
  deepfakeScore?: number | null;
  mlStatus?: string;
}

interface Props {
  chunks: PlayerChunk[];
  activeSequence: number | null;
  onActiveChange: (seq: number | null) => void;
}

export interface SessionPlayerHandle {
  seek: (sequence: number) => void;
  play: (sequence: number) => void;
}

export const SessionPlayer = forwardRef<SessionPlayerHandle, Props>(function SessionPlayer(
  { chunks, activeSequence, onActiveChange }: Props, ref) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [name, setName] = useState<string>('');
  const [playing, setPlaying] = useState(false);
  const [t, setT] = useState(0);
  const [dur, setDur] = useState(0);

  // Median chunk length is more robust than the first or last one: the final
  // chunk of a call is typically a partial.
  const chunkMs = useMemo(() => {
    const ds = chunks.map(c => c.durationMs).filter((d): d is number => !!d).sort((a, b) => a - b);
    return ds.length ? ds[Math.floor(ds.length / 2)] : 3000;
  }, [chunks]);

  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);

  const pick = (f: File | null) => {
    if (!f) return;
    if (url) URL.revokeObjectURL(url);
    setUrl(URL.createObjectURL(f));
    setName(f.name);
    setT(0);
    onActiveChange(null);
  };

  const onTime = () => {
    const a = audioRef.current;
    if (!a) return;
    setT(a.currentTime);
    const idx = Math.floor((a.currentTime * 1000) / chunkMs);
    const hit = chunks.find(c => c.sequence === idx);
    onActiveChange(hit ? hit.sequence : null);
  };

  const seekTo = (seq: number) => {
    const a = audioRef.current;
    if (!a) return;
    a.currentTime = (seq * chunkMs) / 1000;
    setT(a.currentTime);
    onActiveChange(seq);
  };
  // the parent's chunk cards seek through this handle
  const playChunk = (seq: number) => {
    seekTo(seq);
    void audioRef.current?.play();
  };
  useImperativeHandle(ref, () => ({ seek: seekTo, play: playChunk }), [chunkMs, chunks]);

  const fmt = (s: number) =>
    `${Math.floor(s / 60)}:${Math.floor(s % 60).toString().padStart(2, '0')}`;

  if (!url) {
    return (
      <label className="flex items-center gap-3 text-xs text-slate-400 bg-slate-900/60 border border-dashed border-slate-700 rounded-xl px-4 py-3 cursor-pointer hover:border-indigo-500/60 transition-colors w-fit">
        <Upload className="w-4 h-4" />
        <span>Load the streamed file to follow along — stays on your machine</span>
        <input type="file" accept="audio/*" className="hidden"
               onChange={e => pick(e.target.files?.[0] ?? null)} />
      </label>
    );
  }

  const pct = dur ? (t / dur) * 100 : 0;

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-3">
      <audio
        ref={audioRef}
        src={url}
        onTimeUpdate={onTime}
        onLoadedMetadata={e => setDur((e.target as HTMLAudioElement).duration)}
        onPlay={() => setPlaying(true)}
        onPause={() => { setPlaying(false); }}
        onEnded={() => { setPlaying(false); onActiveChange(null); }}
      />

      <div className="flex items-center gap-3">
        <button
          onClick={() => { const a = audioRef.current; if (!a) return; playing ? a.pause() : a.play(); }}
          className="w-9 h-9 shrink-0 rounded-full bg-indigo-600 hover:bg-indigo-500 flex items-center justify-center text-white transition-colors"
          aria-label={playing ? 'Pause' : 'Play'}
        >
          {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
        </button>

        <div className="min-w-0 flex-1">
          <div className="text-xs text-slate-300 truncate">{name}</div>
          <div className="text-[10px] text-slate-500 font-mono">
            {fmt(t)} / {fmt(dur)} · chunk {activeSequence ?? '—'} · {chunkMs} ms per chunk
          </div>
        </div>

        <button onClick={() => { setUrl(null); setName(''); onActiveChange(null); }}
                className="text-slate-500 hover:text-slate-300" aria-label="Clear file">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Chunk ribbon: one segment per chunk, coloured by its verdict, with the
          playhead over the top. Clicking a segment seeks to that chunk. */}
      <div className="relative h-6 rounded-md overflow-hidden bg-slate-800 flex gap-px">
        {chunks.map(c => {
          const s = c.deepfakeScore;
          const tone =
            c.mlStatus === 'PENDING' || s == null ? 'bg-slate-700'
            : s > 0.5 ? 'bg-red-500/80' : 'bg-emerald-500/70';
          const active = c.sequence === activeSequence;
          return (
            <button
              key={c.sequence}
              onClick={() => seekTo(c.sequence)}
              title={`Chunk ${c.sequence}${s != null ? ` — ${(s * 100).toFixed(1)}%` : ''}`}
              className={`flex-1 min-w-[2px] ${tone} ${active ? 'ring-2 ring-inset ring-white brightness-125' : 'hover:brightness-110'} transition-all`}
            />
          );
        })}
        <div className="absolute top-0 bottom-0 w-px bg-white pointer-events-none"
             style={{ left: `${pct}%` }} />
      </div>
    </div>
  );
});
