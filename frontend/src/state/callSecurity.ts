import { useState, useEffect, useCallback } from 'react';
import { CallSecurityState, SecurityAlert } from '../types/security';
import { wsClient } from '../api/websocket';

export function useCallSecurity() {
  const [state, setState] = useState<CallSecurityState>({
    callId: "",
    riskScore: 0,
    riskLevel: "LOW",
    connectionStatus: "DISCONNECTED"
  });

  useEffect(() => {
    // Initial connect
    setState(prev => ({ ...prev, connectionStatus: "CONNECTING" }));
    wsClient.connect();

    const unsubscribe = wsClient.onMessage((event) => {
      switch (event.type) {
        case "CallStarted":
          setState(prev => ({
            ...prev,
            callId: event.call_id,
            caller: event.caller,
            claimedIdentity: event.claimed_identity,
            connectionStatus: "CONNECTED",
            alert: undefined
          }));
          break;
        case "RiskScoreUpdate":
          setState(prev => ({
            ...prev,
            riskScore: event.risk_score,
            riskLevel: event.risk_level,
            spoofProbability: event.spoof_probability,
            speakerSimilarity: event.speaker_similarity,
            prosodyAnomaly: event.prosody_anomaly,
            recommendedAction: event.recommended_action
          }));
          break;
        case "SecurityAlert":
          setState(prev => ({
            ...prev,
            alert: event
          }));
          break;
        case "InferenceStatus":
          setState(prev => ({
            ...prev,
            connectionStatus: event.status === "ACTIVE" ? "CONNECTED" : "DEGRADED"
          }));
          break;
        case "CallEnded":
          setState(prev => ({ ...prev, connectionStatus: "DISCONNECTED" }));
          break;
      }
    });

    return () => {
      unsubscribe();
      wsClient.disconnect();
    };
  }, []);

  const connect = useCallback(() => {
    setState(prev => ({ ...prev, connectionStatus: "CONNECTING" }));
    wsClient.connect();
  }, []);

  const disconnect = useCallback(() => {
    wsClient.disconnect();
    setState(prev => ({ ...prev, connectionStatus: "DISCONNECTED" }));
  }, []);

  return { state, connect, disconnect };
}
