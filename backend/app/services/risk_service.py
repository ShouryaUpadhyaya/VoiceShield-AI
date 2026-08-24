def calculate_risk(deepfake_prob: float, speaker_match: float, prosody_anomaly: float, context_risk: float) -> dict:
    """
    Multi-Signal Risk Fusion Engine.
    Combines:
    - deepfake_prob: 0.0 to 1.0 (High is bad)
    - speaker_match: 0.0 to 1.0 (Low is bad -> so we use 1 - speaker_match)
    - prosody_anomaly: 0.0 to 1.0 (High is bad)
    - context_risk: 0.0 to 1.0 (High is bad)
    """
    
    speaker_mismatch = 1.0 - speaker_match
    
    # Weights for each signal
    w_df = 0.40
    w_sm = 0.25
    w_pa = 0.15
    w_cr = 0.20
    
    base_score = (
        (deepfake_prob * w_df) +
        (speaker_mismatch * w_sm) +
        (prosody_anomaly * w_pa) +
        (context_risk * w_cr)
    ) * 100
    
    final_score = int(min(max(base_score, 0), 100))
    
    if final_score < 40:
        level = 'LOW'
        action = 'CONTINUE'
    elif final_score < 75:
        level = 'MEDIUM'
        action = 'WARNING_SECONDARY_VERIFICATION'
    else:
        level = 'HIGH'
        action = 'BLOCK_AND_ESCALATE'
        
    return {
        "risk_score": final_score,
        "risk_level": level,
        "recommended_action": action,
        "fusion_breakdown": {
            "deepfake_contribution": round(deepfake_prob * w_df * 100, 1),
            "speaker_mismatch_contribution": round(speaker_mismatch * w_sm * 100, 1),
            "prosody_contribution": round(prosody_anomaly * w_pa * 100, 1),
            "context_contribution": round(context_risk * w_cr * 100, 1)
        }
    }
