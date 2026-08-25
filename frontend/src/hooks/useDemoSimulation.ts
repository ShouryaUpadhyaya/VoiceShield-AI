import { useState, useEffect, useCallback } from 'react';

export type DemoCallRisk = 'SAFE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface DemoCall {
  id: string;
  caller: string;
  riskLevel: DemoCallRisk;
  score: number; // 0 to 100
  duration: string;
  timestamp: Date;
  issue?: string;
}

export function useDemoSimulation() {
  const [activeCalls, setActiveCalls] = useState<DemoCall[]>([]);
  const [totalVerifications, setTotalVerifications] = useState(1248);
  const [nodeHealth, setNodeHealth] = useState(100);

  // Randomize metrics slightly every few seconds to make it look alive
  useEffect(() => {
    const interval = setInterval(() => {
      setTotalVerifications(prev => prev + Math.floor(Math.random() * 3));
      setNodeHealth(prev => {
        const jitter = Math.random() > 0.8 ? (Math.random() * 2 - 1) : 0;
        return Math.min(100, Math.max(95, prev + jitter));
      });
      
      // Update durations
      setActiveCalls(prev => prev.map(call => {
        const diffInSeconds = Math.floor((new Date().getTime() - call.timestamp.getTime()) / 1000);
        const mins = Math.floor(diffInSeconds / 60);
        const secs = diffInSeconds % 60;
        return {
          ...call,
          duration: `${mins}:${secs.toString().padStart(2, '0')}`
        };
      }));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const generateId = () => Math.random().toString(36).substring(2, 9);
  
  const getRandomCaller = () => {
    const callers = ['+1 (555) 019-2834', '+44 7700 900077', 'Unknown Caller', 'SIP/Alice', 'SIP/Bob', '+1 (800) 123-4567'];
    return callers[Math.floor(Math.random() * callers.length)];
  };

  const injectSpamCall = useCallback(() => {
    const newCall: DemoCall = {
      id: generateId(),
      caller: getRandomCaller(),
      riskLevel: 'CRITICAL',
      score: 90 + Math.floor(Math.random() * 10),
      duration: '0:00',
      timestamp: new Date(),
      issue: 'Synthetic Voice Detected'
    };
    setActiveCalls(prev => [newCall, ...prev]);
  }, []);

  const injectCleanCall = useCallback(() => {
    const newCall: DemoCall = {
      id: generateId(),
      caller: getRandomCaller(),
      riskLevel: 'SAFE',
      score: Math.floor(Math.random() * 15),
      duration: '0:00',
      timestamp: new Date()
    };
    setActiveCalls(prev => [newCall, ...prev]);
  }, []);

  const injectSuspiciousCall = useCallback(() => {
    const newCall: DemoCall = {
      id: generateId(),
      caller: getRandomCaller(),
      riskLevel: 'HIGH',
      score: 75 + Math.floor(Math.random() * 14),
      duration: '0:00',
      timestamp: new Date(),
      issue: 'Prosody Mismatch'
    };
    setActiveCalls(prev => [newCall, ...prev]);
  }, []);

  const clearAll = useCallback(() => {
    setActiveCalls([]);
  }, []);

  const resolveCall = useCallback((id: string) => {
    setActiveCalls(prev => prev.filter(c => c.id !== id));
  }, []);

  return {
    activeCalls,
    totalVerifications,
    nodeHealth,
    injectSpamCall,
    injectCleanCall,
    injectSuspiciousCall,
    clearAll,
    resolveCall
  };
}
