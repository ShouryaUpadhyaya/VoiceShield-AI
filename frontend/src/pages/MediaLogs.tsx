import React, { useEffect, useState, useRef } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { PhoneCall, PhoneOff, Activity, Copy, CheckCircle2, Mic } from 'lucide-react';

interface CallMetadata {
  "x-call_id"?: string;
  "x-caller"?: string;
  "x-callee"?: string;
  [key: string]: string | undefined;
}

interface Call {
  id: string;
  status: 'active' | 'ended';
  metadata: CallMetadata;
  total_bytes: number;
  start_time: string;
  end_time?: string;
}

interface GraphData {
  time: string;
  rms: number;
  vad: number;
}

export const MediaLogs: React.FC = () => {
  const [logs, setLogs] = useState<{timestamp: string, message: string}[]>([]);
  const [calls, setCalls] = useState<Record<string, Call>>({});
  const [graphData, setGraphData] = useState<GraphData[]>([]);
  const [spectrums, setSpectrums] = useState<number[][]>([]);
  const [vadState, setVadState] = useState<boolean>(false);
  const [copied, setCopied] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const sipUri = "sip:test_call@10.59.60.11:5060";

  useEffect(() => {
    // Fetch initial calls
    fetch('http://localhost:8005/api/calls')
      .then(res => res.json())
      .then(data => setCalls(data.calls || {}))
      .catch(err => console.error("Failed to fetch initial calls", err));

    const eventSource = new EventSource('http://localhost:8005/logs');

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'log') {
          setLogs((prev) => [...prev, {timestamp: data.timestamp, message: data.message}].slice(-100));
        } else if (data.type === 'call_start' || data.type === 'call_end' || data.type === 'metadata_update') {
          if (data.call) {
            setCalls((prev) => ({ ...prev, [data.call.id]: data.call }));
          }
        } else if (data.type === 'audio_chunk') {
          // Update total bytes
          setCalls((prev) => {
            const call = prev[data.call_id];
            if (!call) return prev;
            return {
              ...prev,
              [data.call_id]: { ...call, total_bytes: data.total_bytes }
            };
          });

          const rms = data.rms || 0;
          const vad = data.vad ? 1 : 0;
          setVadState(data.vad || false);

          setGraphData((prev) => {
            const newGraph = [...prev, { time: data.timestamp, rms: rms, vad: vad }];
            return newGraph.slice(-40); 
          });

          if (data.spectrum) {
            setSpectrums((prev) => [...prev, data.spectrum].slice(-40));
          }
        }
      } catch (e) {
        setLogs((prev) => [...prev, {timestamp: new Date().toLocaleTimeString(), message: event.data}].slice(-100));
      }
    };

    eventSource.onerror = (err) => console.error("SSE Error:", err);
    return () => eventSource.close();
  }, []);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Draw spectrogram
  useEffect(() => {
    if (!canvasRef.current || spectrums.length === 0) return;
    const ctx = canvasRef.current.getContext('2d');
    if (!ctx) return;
    
    const width = canvasRef.current.width;
    const height = canvasRef.current.height;
    ctx.clearRect(0, 0, width, height);
    
    const blockWidth = width / 40;
    const bins = spectrums[0].length || 32;
    const blockHeight = height / bins;

    spectrums.forEach((spec, timeIndex) => {
      spec.forEach((val, freqIndex) => {
        // Map value to color (blue -> green -> yellow -> red)
        const intensity = Math.min(255, Math.max(0, val / 100));
        ctx.fillStyle = `rgb(${intensity}, ${intensity > 128 ? 255 - intensity : intensity}, ${255 - intensity})`;
        ctx.fillRect(timeIndex * blockWidth, height - (freqIndex * blockHeight), blockWidth, blockHeight);
      });
    });
  }, [spectrums]);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(sipUri);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const activeCall = Object.values(calls).find(c => c.status === 'active');
  const duration = activeCall ? Math.floor((new Date().getTime() - new Date(activeCall.start_time).getTime()) / 1000) : 0;
  const formatDuration = (d: number) => `${Math.floor(d / 60).toString().padStart(2, '0')}:${(d % 60).toString().padStart(2, '0')}`;
  const totalFrames = activeCall ? Math.floor(activeCall.total_bytes / 320) : 0; // Assuming 320 bytes per frame

  return (
    <div className="min-h-screen bg-black text-gray-300 p-8 font-mono">
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Terminal Header */}
        <div className="border border-green-500/30 p-1 rounded-sm bg-black relative">
          <div className="absolute -top-3 left-4 bg-black px-2 text-green-500 font-bold text-sm tracking-widest flex items-center gap-2">
            VOICEGUARD MEDIA GATEWAY
          </div>
          <div className="absolute -top-3 right-4 bg-black px-2 text-green-500 font-bold text-sm flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${activeCall ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
            {activeCall ? 'STREAMING' : 'IDLE'}
          </div>

          <div className="mt-6 p-4">
            
            {/* CALL SESSION */}
            <div className="mb-4">
              <h3 className="text-gray-500 text-xs mb-2">CALL SESSION</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-green-400">
                <div><span className="text-gray-500">Call ID:</span> {activeCall?.metadata['x-call_id']?.substring(0,8) || 'NONE'}</div>
                <div><span className="text-gray-500">Protocol:</span> WebRTC/SIP</div>
                <div><span className="text-gray-500">Codec:</span> PCM/L16</div>
                <div><span className="text-gray-500">Sample Rate:</span> 16 kHz</div>
                <div><span className="text-gray-500">Duration:</span> {formatDuration(duration)}</div>
                <div><span className="text-gray-500">Frames:</span> {totalFrames.toLocaleString()}</div>
                <div className="col-span-2 flex items-center gap-2 text-blue-400">
                  <span className="text-gray-500">URI:</span> {sipUri}
                  <button onClick={copyToClipboard} className="hover:text-white transition">
                    {copied ? <CheckCircle2 size={14}/> : <Copy size={14}/>}
                  </button>
                </div>
              </div>
            </div>

            <div className="border-t border-green-500/30 my-4"></div>

            {/* GRAPHS */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Waveform */}
              <div>
                <h3 className="text-gray-500 text-xs text-center mb-2">LIVE AUDIO WAVEFORM (RMS)</h3>
                <div className="h-40 bg-gray-900 border border-gray-800 rounded">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={graphData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                      <Area type="monotone" dataKey="rms" stroke="#10b981" fill="#10b981" fillOpacity={0.3} isAnimationActive={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
              
              {/* Spectrogram */}
              <div>
                <h3 className="text-gray-500 text-xs text-center mb-2">SPECTROGRAM (FFT)</h3>
                <div className="h-40 bg-gray-900 border border-gray-800 rounded flex items-center justify-center relative">
                  <canvas 
                    ref={canvasRef} 
                    width={400} 
                    height={160} 
                    className="w-full h-full object-fill opacity-80" 
                  />
                  {!activeCall && <span className="absolute text-gray-700">AWAITING AUDIO</span>}
                </div>
              </div>
            </div>

            <div className="border-t border-green-500/30 my-4"></div>

            {/* VAD TIMELINE */}
            <div>
              <h3 className="text-gray-500 text-xs mb-2">SPEECH ACTIVITY (VAD)</h3>
              <div className="h-4 flex rounded overflow-hidden bg-gray-900">
                {graphData.map((d, i) => (
                  <div key={i} className="flex-1" style={{ backgroundColor: d.vad ? '#10b981' : '#1f2937' }}></div>
                ))}
              </div>
              <div className="mt-1 text-right text-xs">
                 <span className={vadState ? 'text-green-500' : 'text-gray-500'}>
                   {vadState ? 'SPEECH DETECTED' : 'SILENCE'}
                 </span>
              </div>
            </div>

            <div className="border-t border-green-500/30 my-4"></div>

            {/* METRICS */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-gray-500 text-xs">AUDIO QUALITY</div>
                <div className="text-green-400 font-bold">GOOD</div>
              </div>
              <div className="border-l border-green-500/30">
                <div className="text-gray-500 text-xs">STREAM LATENCY</div>
                <div className="text-yellow-400 font-bold">~42 ms</div>
              </div>
              <div className="border-l border-green-500/30">
                <div className="text-gray-500 text-xs">PACKET LOSS</div>
                <div className="text-green-400 font-bold">0.0%</div>
              </div>
              <div className="border-l border-green-500/30">
                <div className="text-gray-500 text-xs">AI ENGINE</div>
                <div className={activeCall ? "text-green-400 font-bold" : "text-gray-500 font-bold"}>
                  {activeCall ? 'CONNECTED' : 'IDLE'}
                </div>
              </div>
            </div>

          </div>
        </div>

        {/* Console Logs */}
        <div className="bg-black border border-gray-800 p-4 h-[300px] overflow-y-auto text-xs font-mono">
          <div className="text-gray-500 mb-2">// MEDIA GATEWAY EVENT STREAM</div>
          {logs.length === 0 && <div className="text-gray-700 animate-pulse">Initializing socket...</div>}
          {logs.map((log, index) => (
            <div key={index} className="hover:bg-gray-900 px-1 py-0.5">
              <span className="text-blue-500 mr-2">[{log.timestamp}]</span>
              <span className="text-gray-300">{log.message}</span>
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>

      </div>
    </div>
  );
};
