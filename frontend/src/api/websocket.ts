import { WebSocketEvent, RiskLevel } from '../types/security';

type EventCallback = (event: WebSocketEvent) => void;

class MockWebSocketClient {
  private listeners: EventCallback[] = [];
  private isConnected = false;
  private demoInterval: ReturnType<typeof setInterval> | null = null;

  connect() {
    this.isConnected = true;
    setTimeout(() => {
      // Automatically start demo when connected for now
      this.startDemoCall();
    }, 1000);
  }

  disconnect() {
    this.isConnected = false;
    if (this.demoInterval) {
      clearInterval(this.demoInterval);
      this.demoInterval = null;
    }
  }

  onMessage(callback: EventCallback) {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter(cb => cb !== callback);
    };
  }

  private dispatch(event: WebSocketEvent) {
    this.listeners.forEach(cb => cb(event));
  }

  private startDemoCall() {
    if (this.demoInterval) clearInterval(this.demoInterval);
    
    let step = 0;
    const callId = "demo-call-123";
    
    this.dispatch({
      type: "CallStarted",
      call_id: callId,
      caller: "+91 98765 43210",
      claimed_identity: "Rahul Sharma (CFO)",
      timestamp: Date.now()
    });

    const scenario = [
      { score: 18, level: "LOW" as RiskLevel },
      { score: 22, level: "LOW" as RiskLevel },
      { score: 28, level: "LOW" as RiskLevel },
      { score: 35, level: "MEDIUM" as RiskLevel },
      { score: 46, level: "MEDIUM" as RiskLevel },
      { score: 54, level: "MEDIUM" as RiskLevel },
      { score: 68, level: "HIGH" as RiskLevel },
      { score: 75, level: "HIGH" as RiskLevel },
      { score: 87, level: "CRITICAL" as RiskLevel },
      { score: 92, level: "CRITICAL" as RiskLevel },
    ];

    this.demoInterval = setInterval(() => {
      if (step < scenario.length) {
        const state = scenario[step];
        this.dispatch({
          type: "RiskScoreUpdate",
          call_id: callId,
          timestamp: Date.now(),
          risk_score: state.score,
          risk_level: state.level,
          spoof_probability: state.score / 100 + 0.05,
          speaker_similarity: 1 - (state.score / 100),
          prosody_anomaly: state.score / 100,
          recommended_action: state.level === "CRITICAL" ? "SECONDARY_VERIFICATION" : state.level === "HIGH" ? "CONTINUE_MONITORING" : "NONE"
        });

        if (state.level === "CRITICAL" && step === scenario.length - 2) {
          this.dispatch({
            type: "SecurityAlert",
            severity: "CRITICAL",
            risk_score: state.score,
            recommended_action: "SECONDARY_VERIFICATION"
          });
        }
        step++;
      } else {
        clearInterval(this.demoInterval!);
      }
    }, 2000);
  }
}

export const wsClient = new MockWebSocketClient();
