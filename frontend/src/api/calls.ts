import { RiskLevel } from '../types/security';

export interface DashboardCallSummary {
  id: string;
  caller: string;
  duration: string;
  riskLevel: RiskLevel;
  score: number;
}

export const fetchActiveCalls = async (): Promise<DashboardCallSummary[]> => {
  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, 500));
  
  return [
    { id: '1001', caller: '+91 98765 43210', duration: '04:12', riskLevel: 'LOW', score: 12 },
    { id: '1002', caller: '+91 87654 32109', duration: '01:45', riskLevel: 'MEDIUM', score: 45 },
    { id: '1003', caller: '+1 415 555 0198', duration: '00:30', riskLevel: 'CRITICAL', score: 89 },
    { id: '1004', caller: '+44 20 7123 4567', duration: '12:05', riskLevel: 'LOW', score: 5 },
  ];
};

export const verifyCaller = async (callId: string, method: string): Promise<boolean> => {
  await new Promise(resolve => setTimeout(resolve, 1500));
  return true; // Mock successful verification
};
