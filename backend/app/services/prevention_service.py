def trigger_prevention(risk_score: int, risk_level: str) -> dict:
    if risk_level == 'HIGH':
        return {
            "status": "TRANSACTION_HELD",
            "message": "Transaction suspended due to high impersonation risk.",
            "verification_required": ["MFA", "SUPERVISOR_APPROVAL"]
        }
    elif risk_level == 'MEDIUM':
        return {
            "status": "WARNING",
            "message": "Proceed with caution. Secondary verification recommended.",
            "verification_required": ["MFA"]
        }
    else:
        return {
            "status": "ALLOWED",
            "message": "Transaction cleared securely.",
            "verification_required": []
        }
