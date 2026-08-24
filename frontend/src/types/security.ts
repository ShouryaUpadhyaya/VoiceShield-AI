export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface SecurityAlert {
  type: "SecurityAlert";
  severity: RiskLevel;
  risk_score: number;
  recommended_action: string;
}

export interface CallSecurityState {
  callId: string;
  caller?: string;
  claimedIdentity?: string;
  duration?: number;
  
  riskScore: number;
  riskLevel: RiskLevel;
  
  spoofProbability?: number;
  speakerSimilarity?: number;
  prosodyAnomaly?: number;
  
  recommendedAction?: string;
  
  connectionStatus: "CONNECTED" | "CONNECTING" | "DISCONNECTED" | "DEGRADED";
  
  alert?: SecurityAlert;
}

export type WebSocketEvent = 
  | { type: "CallStarted"; call_id: string; caller: string; claimed_identity: string; timestamp: number }
  | { 
      type: "RiskScoreUpdate"; 
      call_id: string; 
      timestamp: number; 
      risk_score: number; 
      risk_level: RiskLevel; 
      spoof_probability: number; 
      speaker_similarity: number; 
      prosody_anomaly: number; 
      recommended_action: string 
    }
  | SecurityAlert
  | { type: "InferenceStatus"; status: "ACTIVE" | "DEGRADED" }
  | { type: "CallEnded"; call_id: string; timestamp: number };
