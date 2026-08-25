import React, { useEffect, useState, useRef } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { PhoneCall, PhoneOff, Activity, Copy, CheckCircle2, Settings, MonitorPlay } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"

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
  
  // Routing Configuration State
  const [routingType, setRoutingType] = useState('internal');
  const [providerName, setProviderName] = useState('twilio_trunk');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [domain, setDomain] = useState('');
  const [destRegex, setDestRegex] = useState('^(\\d{10})$');
  const [useManualIp, setUseManualIp] = useState(false);
  const [manualIp, setManualIp] = useState('10.59.60.11');
  const [isSaving, setIsSaving] = useState(false);
  
  const logsEndRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const sipUri = `sip:test_call@${window.location.hostname}:5060`;

  useEffect(() => {
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
  
  const handleSaveRouting = async () => {
    setIsSaving(true);
    try {
      const res = await fetch('http://localhost:8005/api/routing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          routingType,
          providerName,
          username,
          password,
          domain,
          destinationRegex: destRegex,
          useManualIp,
          manualIp
        })
      });
      const data = await res.json();
      if (data.status === 'success') {
        alert("Routing updated successfully! FreeSWITCH XML was reloaded.");
      } else {
        alert("Failed to update routing: " + data.message);
      }
    } catch (e: any) {
      alert("Error: " + e.message);
    }
    setIsSaving(false);
  };

  const activeCall = Object.values(calls).find(c => c.status === 'active');
  const duration = activeCall ? Math.floor((new Date().getTime() - new Date(activeCall.start_time).getTime()) / 1000) : 0;
  const formatDuration = (d: number) => `${Math.floor(d / 60).toString().padStart(2, '0')}:${(d % 60).toString().padStart(2, '0')}`;
  const totalFrames = activeCall ? Math.floor(activeCall.total_bytes / 320) : 0; 

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 p-8 font-sans">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row justify-between items-center bg-neutral-900 border border-neutral-800 rounded-xl p-6 shadow-2xl">
          <div className="flex items-center gap-4">
            <div className="bg-blue-600 p-3 rounded-full shadow-lg shadow-blue-900/50">
              <Activity className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">VoiceGuard Gateway</h1>
              <p className="text-neutral-400 text-sm">Real-time Telephony & Media Analysis</p>
            </div>
          </div>
          <div className="flex items-center gap-3 bg-neutral-950 p-3 rounded-lg border border-neutral-800 mt-4 md:mt-0">
            <span className="text-sm text-neutral-500 font-mono">SIP URI:</span>
            <span className="text-blue-400 font-mono text-sm font-bold">{sipUri}</span>
            <Button variant="ghost" size="icon" onClick={copyToClipboard} className="h-8 w-8 text-neutral-400 hover:text-white">
              {copied ? <CheckCircle2 size={16} className="text-green-500" /> : <Copy size={16} />}
            </Button>
          </div>
        </div>

        <Tabs defaultValue="dashboard" className="w-full">
          <TabsList className="bg-neutral-900 border border-neutral-800 mb-6">
            <TabsTrigger value="dashboard" className="data-[state=active]:bg-neutral-800 data-[state=active]:text-white">
              <MonitorPlay className="w-4 h-4 mr-2" /> Dashboard
            </TabsTrigger>
            <TabsTrigger value="routing" className="data-[state=active]:bg-neutral-800 data-[state=active]:text-white">
              <Settings className="w-4 h-4 mr-2" /> External Routing
            </TabsTrigger>
          </TabsList>
          
          <TabsContent value="dashboard" className="space-y-6 mt-0">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* Main Graphs Panel */}
              <div className="lg:col-span-2 space-y-6">
                
                {/* Session Card */}
                <Card className="bg-neutral-900 border-neutral-800">
                  <CardHeader className="pb-2">
                    <div className="flex justify-between items-center">
                      <CardTitle className="text-lg flex items-center gap-2">
                        Call Session
                      </CardTitle>
                      {activeCall ? (
                        <Badge variant="default" className="bg-green-600 hover:bg-green-700 animate-pulse text-white font-bold flex gap-1 items-center">
                          <PhoneCall size={14} /> CONNECTED
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-neutral-500 border-neutral-700 flex gap-1 items-center">
                          <PhoneOff size={14} /> DISCONNECTED
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mt-2">
                      <div><span className="text-neutral-500 block text-xs font-semibold mb-1">CALL ID</span> <span className="font-mono text-blue-400">{activeCall?.metadata['x-call_id']?.substring(0,8) || 'N/A'}</span></div>
                      <div><span className="text-neutral-500 block text-xs font-semibold mb-1">CODEC</span> <span className="font-mono">PCM L16</span></div>
                      <div><span className="text-neutral-500 block text-xs font-semibold mb-1">DURATION</span> <span className="font-mono">{formatDuration(duration)}</span></div>
                      <div><span className="text-neutral-500 block text-xs font-semibold mb-1">FRAMES</span> <span className="font-mono">{totalFrames.toLocaleString()}</span></div>
                    </div>
                  </CardContent>
                </Card>

                {/* DSP Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <Card className="bg-neutral-900 border-neutral-800">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm text-neutral-400">Audio Waveform (RMS)</CardTitle>
                    </CardHeader>
                    <CardContent className="h-40 p-4 pt-0">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={graphData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                          <Area type="monotone" dataKey="rms" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} isAnimationActive={false} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                  
                  <Card className="bg-neutral-900 border-neutral-800">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm text-neutral-400">Spectrogram (FFT)</CardTitle>
                    </CardHeader>
                    <CardContent className="h-40 p-4 pt-0">
                      <div className="w-full h-full bg-neutral-950 rounded border border-neutral-800 relative flex items-center justify-center">
                        <canvas ref={canvasRef} width={400} height={160} className="w-full h-full object-fill opacity-90" />
                        {!activeCall && <span className="absolute text-neutral-600 font-mono text-sm">NO AUDIO</span>}
                      </div>
                    </CardContent>
                  </Card>
                </div>
                
                {/* VAD Bar */}
                <Card className="bg-neutral-900 border-neutral-800">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-neutral-400 flex justify-between">
                      <span>Speech Activity Timeline</span>
                      <span className={vadState ? 'text-green-500 font-bold' : 'text-neutral-500'}>
                        {vadState ? 'SPEECH DETECTED' : 'SILENCE'}
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-6 flex rounded overflow-hidden bg-neutral-950 border border-neutral-800">
                      {graphData.map((d, i) => (
                        <div key={i} className="flex-1 transition-colors duration-100" style={{ backgroundColor: d.vad ? '#22c55e' : 'transparent' }}></div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

              </div>

              {/* Side Panel: Logs & History */}
              <div className="space-y-6">
                <Card className="bg-neutral-900 border-neutral-800 h-full flex flex-col max-h-[800px]">
                  <CardHeader>
                    <CardTitle className="text-sm">Gateway Event Logs</CardTitle>
                  </CardHeader>
                  <CardContent className="flex-1 overflow-y-auto font-mono text-xs text-neutral-400 p-4 bg-black rounded-b-xl">
                    {logs.map((log, i) => (
                      <div key={i} className="mb-1">
                        <span className="text-blue-500">[{log.timestamp}]</span> <span className="text-neutral-300">{log.message}</span>
                      </div>
                    ))}
                    <div ref={logsEndRef} />
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>
          
          <TabsContent value="routing" className="mt-0">
            <Card className="bg-neutral-900 border-neutral-800 max-w-2xl mx-auto">
              <CardHeader>
                <CardTitle>SIP Routing Configuration</CardTitle>
                <CardDescription className="text-neutral-400">Configure how VoiceGuard routes calls. Use a SIP Trunk (e.g. Twilio) to bridge calls to external numbers.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-3">
                  <Label>Routing Mode</Label>
                  <div className="flex gap-4">
                    <Button 
                      variant={routingType === 'internal' ? 'default' : 'outline'} 
                      onClick={() => setRoutingType('internal')}
                      className={routingType === 'internal' ? 'bg-blue-600 hover:bg-blue-700' : 'border-neutral-700 text-neutral-300'}
                    >
                      Internal Test (Echo)
                    </Button>
                    <Button 
                      variant={routingType === 'external' ? 'default' : 'outline'} 
                      onClick={() => setRoutingType('external')}
                      className={routingType === 'external' ? 'bg-blue-600 hover:bg-blue-700' : 'border-neutral-700 text-neutral-300'}
                    >
                      External Trunk Bridge
                    </Button>
                  </div>
                </div>

                {routingType === 'external' && (
                  <div className="space-y-4 animate-in fade-in slide-in-from-top-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Provider Name</Label>
                        <Input className="bg-neutral-950 border-neutral-800" value={providerName} onChange={e => setProviderName(e.target.value)} placeholder="twilio" />
                      </div>
                      <div className="space-y-2">
                        <Label>SIP Domain / Realm</Label>
                        <Input className="bg-neutral-950 border-neutral-800" value={domain} onChange={e => setDomain(e.target.value)} placeholder="xyz.sip.twilio.com" />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Username</Label>
                        <Input className="bg-neutral-950 border-neutral-800" value={username} onChange={e => setUsername(e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Password</Label>
                        <Input className="bg-neutral-950 border-neutral-800" type="password" value={password} onChange={e => setPassword(e.target.value)} />
                      </div>
                    </div>
                  </div>
                )}
                
                <div className="space-y-2">
                  <Label>Destination Match Regex</Label>
                  <Input className="bg-neutral-950 border-neutral-800 font-mono text-sm" value={destRegex} onChange={e => setDestRegex(e.target.value)} placeholder="^(\d{10})$" />
                  <p className="text-xs text-neutral-500">Regular expression for matching dialed numbers (e.g., `^(\d{10})$` for 10-digit phones, or `^.*$` for all).</p>
                </div>

                <div className="p-4 border border-neutral-800 rounded-lg space-y-4 bg-neutral-950">
                  <div className="flex items-center gap-2">
                    <input type="checkbox" id="manual-ip" checked={useManualIp} onChange={e => setUseManualIp(e.target.checked)} className="rounded border-neutral-700 bg-neutral-900" />
                    <Label htmlFor="manual-ip">Use Manual IP Override (Advanced)</Label>
                  </div>
                  {useManualIp && (
                    <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
                      <Label>Host LAN IP Address</Label>
                      <Input className="bg-neutral-900 border-neutral-800 font-mono text-sm" value={manualIp} onChange={e => setManualIp(e.target.value)} placeholder="192.168.1.5" />
                      <p className="text-xs text-neutral-500">Override `auto-nat` if FreeSWITCH fails to detect your Wi-Fi IP address.</p>
                    </div>
                  )}
                </div>

                <Button onClick={handleSaveRouting} disabled={isSaving} className="w-full bg-green-600 hover:bg-green-700 text-white font-bold">
                  {isSaving ? "Applying..." : "Save & Hot-Reload FreeSWITCH"}
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
          
        </Tabs>
      </div>
    </div>
  );
};
