import React, { useEffect, useState, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { PhoneCall, PhoneOff, Activity, Copy, CheckCircle2 } from 'lucide-react';

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
  bytes: number;
}

export const MediaLogs: React.FC = () => {
  const [logs, setLogs] = useState<{timestamp: string, message: string}[]>([]);
  const [calls, setCalls] = useState<Record<string, Call>>({});
  const [graphData, setGraphData] = useState<GraphData[]>([]);
  const [copied, setCopied] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);

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
          setLogs((prev) => [...prev, {timestamp: data.timestamp, message: data.message}].slice(-50));
        } else if (data.type === 'call_start' || data.type === 'call_end' || data.type === 'metadata_update') {
          if (data.call) {
            setCalls((prev) => ({ ...prev, [data.call.id]: data.call }));
          }
        } else if (data.type === 'audio_chunk') {
          // Update total bytes for the call
          setCalls((prev) => {
            const call = prev[data.call_id];
            if (!call) return prev;
            return {
              ...prev,
              [data.call_id]: { ...call, total_bytes: data.total_bytes }
            };
          });

          // Add to graph data
          setGraphData((prev) => {
            const newGraph = [...prev, { time: data.timestamp, bytes: data.bytes_received }];
            return newGraph.slice(-30); // Keep last 30 data points
          });
        }
      } catch (e) {
        // Fallback for non-JSON logs (e.g. older messages)
        setLogs((prev) => [...prev, {timestamp: new Date().toLocaleTimeString(), message: event.data}].slice(-50));
      }
    };

    eventSource.onerror = (err) => {
      console.error("SSE Error:", err);
    };

    return () => {
      eventSource.close();
    };
  }, []);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(sipUri);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const activeCall = Object.values(calls).find(c => c.status === 'active');

  return (
    <div className="min-h-screen bg-gray-950 text-gray-300 p-8 font-sans">
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Header & Connection Info */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 flex flex-col md:flex-row justify-between items-center shadow-lg">
          <div>
            <h1 className="text-3xl font-bold text-white flex items-center gap-3">
              <Activity className="text-blue-500" /> Media Gateway Dashboard
            </h1>
            <p className="text-gray-400 mt-2">Test your FreeSWITCH media pipeline via SIP.</p>
          </div>
          <div className="mt-4 md:mt-0 bg-black/50 p-4 rounded-lg border border-gray-800 flex items-center gap-4">
            <div>
              <div className="text-sm text-gray-500 font-mono mb-1">SIP Testing URI</div>
              <div className="text-blue-400 font-mono text-lg font-bold">{sipUri}</div>
            </div>
            <button 
              onClick={copyToClipboard}
              className="p-2 hover:bg-gray-800 rounded transition-colors"
              title="Copy SIP URI"
            >
              {copied ? <CheckCircle2 className="text-green-500" /> : <Copy className="text-gray-400" />}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Active Call Status & Graph */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 shadow-lg h-96 flex flex-col">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  Live Audio Stream
                </h2>
                {activeCall ? (
                  <span className="px-3 py-1 bg-green-500/20 text-green-400 text-sm font-bold rounded-full flex items-center gap-2 animate-pulse">
                    <PhoneCall size={16} /> Connected
                  </span>
                ) : (
                  <span className="px-3 py-1 bg-red-500/20 text-red-400 text-sm font-bold rounded-full flex items-center gap-2">
                    <PhoneOff size={16} /> Disconnected
                  </span>
                )}
              </div>
              
              <div className="flex-1 w-full bg-black/30 rounded-lg p-2 border border-gray-800">
                {activeCall && graphData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={graphData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="time" stroke="#9CA3AF" fontSize={12} />
                      <YAxis stroke="#9CA3AF" fontSize={12} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', color: '#fff' }}
                        itemStyle={{ color: '#3B82F6' }}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="bytes" 
                        stroke="#3B82F6" 
                        strokeWidth={3}
                        dot={false}
                        isAnimationActive={false} 
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full w-full flex items-center justify-center text-gray-600 font-mono">
                    Waiting for audio stream...
                  </div>
                )}
              </div>
            </div>

            {/* Call History Table */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 shadow-lg">
              <h2 className="text-xl font-bold text-white mb-4">Call History</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-black/50 text-gray-400 uppercase font-mono">
                    <tr>
                      <th className="px-4 py-3 rounded-tl-lg">Status</th>
                      <th className="px-4 py-3">Caller</th>
                      <th className="px-4 py-3">Callee</th>
                      <th className="px-4 py-3">Total Bytes</th>
                      <th className="px-4 py-3 rounded-tr-lg">Duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.values(calls).length === 0 ? (
                      <tr>
                        <td colSpan={5} className="text-center py-8 text-gray-600">No calls recorded yet.</td>
                      </tr>
                    ) : (
                      Object.values(calls).reverse().map((call) => (
                        <tr key={call.id} className="border-b border-gray-800 hover:bg-black/30 transition-colors">
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded text-xs font-bold ${call.status === 'active' ? 'bg-green-500/20 text-green-400' : 'bg-gray-700 text-gray-300'}`}>
                              {call.status.toUpperCase()}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono">{call.metadata['x-caller'] || 'Unknown'}</td>
                          <td className="px-4 py-3 font-mono">{call.metadata['x-callee'] || 'Unknown'}</td>
                          <td className="px-4 py-3 font-mono text-blue-400">{(call.total_bytes / 1024).toFixed(2)} KB</td>
                          <td className="px-4 py-3 font-mono text-gray-500">
                            {new Date(call.start_time).toLocaleTimeString()}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Raw SSE Logs */}
          <div className="bg-black border border-gray-800 rounded-xl p-4 shadow-lg h-[800px] flex flex-col font-mono text-xs">
            <h2 className="text-lg font-bold text-white mb-4 border-b border-gray-800 pb-2">Terminal Logs</h2>
            <div className="flex-1 overflow-y-auto">
              {logs.length === 0 ? (
                <div className="text-gray-600 animate-pulse mt-4 text-center">Connecting to backend...</div>
              ) : (
                logs.map((log, index) => (
                  <div key={index} className="mb-2 hover:bg-gray-900 p-1 rounded transition-colors break-words">
                    <span className="text-blue-500">[{log.timestamp}]</span> <span className="text-gray-300">{log.message}</span>
                  </div>
                ))
              )}
              <div ref={logsEndRef} />
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};
