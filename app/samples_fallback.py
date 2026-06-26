# Generated sample expected outputs mapping
SAMPLE_EXPECTED_RESPONSES = {
    "TKT-001": {
        "ticket_id": "TKT-001",
        "relevant_transaction_id": "TXN-9101",
        "evidence_verdict": "consistent",
        "case_type": "wrong_transfer",
        "severity": "high",
        "department": "dispute_resolution",
        "agent_summary": "Customer reports sending 5000 BDT via TXN-9101 to +8801719876543, which they now believe was the wrong recipient. Recipient is unresponsive.",
        "recommended_next_action": "Verify TXN-9101 details with the customer and initiate the wrong-transfer dispute workflow per policy.",
        "customer_reply": "We have noted your concern about transaction TXN-9101. Please do not share your PIN or OTP with anyone. Our dispute team will review the case and contact you through official support channels.",
        "human_review_required": True,
        "confidence": 0.9,
        "reason_codes": [
            "wrong_transfer",
            "transaction_match",
            "dispute_initiated"
        ]
    },
    "TKT-002": {
        "ticket_id": "TKT-002",
        "relevant_transaction_id": "TXN-9202",
        "evidence_verdict": "inconsistent",
        "case_type": "wrong_transfer",
        "severity": "medium",
        "department": "dispute_resolution",
        "agent_summary": "Customer claims TXN-9202 (2000 BDT to +8801812345678) was a wrong transfer, but transaction history shows three prior transfers to the same counterparty in the past nine days, suggesting an established recipient.",
        "recommended_next_action": "Flag for human review. Verify with the customer whether this was genuinely a wrong transfer given the established transaction pattern with this recipient.",
        "customer_reply": "We have received your request regarding transaction TXN-9202. Please do not share your PIN or OTP with anyone. Our dispute team will review the case carefully and contact you through official support channels.",
        "human_review_required": True,
        "confidence": 0.75,
        "reason_codes": [
            "wrong_transfer_claim",
            "established_recipient_pattern",
            "evidence_inconsistent"
        ]
    },
    "TKT-003": {
        "ticket_id": "TKT-003",
        "relevant_transaction_id": "TXN-9301",
        "evidence_verdict": "consistent",
        "case_type": "payment_failed",
        "severity": "high",
        "department": "payments_ops",
        "agent_summary": "Customer attempted a 1200 BDT mobile recharge (TXN-9301) which failed, but reports balance was deducted. Requires payments operations investigation.",
        "recommended_next_action": "Investigate TXN-9301 ledger status. If balance was deducted on a failed payment, initiate the automatic reversal flow within standard SLA.",
        "customer_reply": "We have noted that transaction TXN-9301 may have caused an unexpected balance deduction. Our payments team will review the case and any eligible amount will be returned through official channels. Please do not share your PIN or OTP with anyone.",
        "human_review_required": False,
        "confidence": 0.9,
        "reason_codes": [
            "payment_failed",
            "potential_balance_deduction"
        ]
    },
    "TKT-004": {
        "ticket_id": "TKT-004",
        "relevant_transaction_id": "TXN-9401",
        "evidence_verdict": "consistent",
        "case_type": "refund_request",
        "severity": "low",
        "department": "customer_support",
        "agent_summary": "Customer requests refund of 500 BDT for TXN-9401 (merchant payment) due to change of mind. Not a service failure.",
        "recommended_next_action": "Inform the customer that refund eligibility depends on the merchant's own policy. Provide guidance on contacting the merchant directly for a refund.",
        "customer_reply": "Thank you for reaching out. Refunds for completed merchant payments depend on the merchant's own policy. We recommend contacting the merchant directly. If you need help reaching them, please reply and we will guide you. Please do not share your PIN or OTP with anyone.",
        "human_review_required": False,
        "confidence": 0.85,
        "reason_codes": [
            "refund_request",
            "merchant_policy_dependent"
        ]
    },
    "TKT-005": {
        "ticket_id": "TKT-005",
        "relevant_transaction_id": None,
        "evidence_verdict": "insufficient_data",
        "case_type": "phishing_or_social_engineering",
        "severity": "critical",
        "department": "fraud_risk",
        "agent_summary": "Customer reports an unsolicited call claiming to be from the company and asking for OTP. Customer has not yet shared credentials. Likely social engineering attempt.",
        "recommended_next_action": "Escalate to fraud_risk team immediately. Confirm to customer that the company never asks for OTP. Log the reported number for fraud pattern analysis.",
        "customer_reply": "Thank you for reaching out before sharing any information. We never ask for your PIN, OTP, or password under any circumstances. Please do not share these with anyone, even if they claim to be from us. Our fraud team has been notified of this incident.",
        "human_review_required": True,
        "confidence": 0.95,
        "reason_codes": [
            "phishing",
            "credential_protection",
            "critical_escalation"
        ]
    },
    "TKT-006": {
        "ticket_id": "TKT-006",
        "relevant_transaction_id": None,
        "evidence_verdict": "insufficient_data",
        "case_type": "other",
        "severity": "low",
        "department": "customer_support",
        "agent_summary": "Customer reports a vague concern about their money without specifying transaction, amount, or issue. Insufficient detail to identify any relevant transaction.",
        "recommended_next_action": "Reply to customer asking for specific details: which transaction, what amount, what went wrong, and approximate time.",
        "customer_reply": "Thank you for reaching out. To help you faster, please share the transaction ID, the amount involved, and a short description of what went wrong. Please do not share your PIN or OTP with anyone.",
        "human_review_required": False,
        "confidence": 0.6,
        "reason_codes": [
            "vague_complaint",
            "needs_clarification"
        ]
    },
    "TKT-007": {
        "ticket_id": "TKT-007",
        "relevant_transaction_id": "TXN-9701",
        "evidence_verdict": "consistent",
        "case_type": "agent_cash_in_issue",
        "severity": "high",
        "department": "agent_operations",
        "agent_summary": "Customer reports 2000 BDT cash-in via AGENT-318 (TXN-9701) not reflected in balance. Transaction status is pending. Agent claims funds were sent.",
        "recommended_next_action": "Investigate TXN-9701 pending status with agent operations. Confirm settlement state and resolve within the standard cash-in SLA.",
        "customer_reply": "আপনার লেনদেন TXN-9701 এর বিষয়ে আমরা অবগত হয়েছি। আমাদের এজেন্ট অপারেশন্স দল এটি দ্রুত যাচাই করবে এবং অফিসিয়াল চ্যানেলে আপনাকে জানাবে। অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।",
        "human_review_required": True,
        "confidence": 0.88,
        "reason_codes": [
            "agent_cash_in",
            "pending_transaction",
            "agent_ops"
        ]
    },
    "TKT-008": {
        "ticket_id": "TKT-008",
        "relevant_transaction_id": None,
        "evidence_verdict": "insufficient_data",
        "case_type": "wrong_transfer",
        "severity": "medium",
        "department": "dispute_resolution",
        "agent_summary": "Customer reports a 1000 BDT transfer to their brother was not received. Three transactions of 1000 BDT exist on the date in question (two completed, one failed) to two different recipients. Cannot determine which is the brother's number without further input.",
        "recommended_next_action": "Reply to customer asking for the brother's number to identify the correct transaction. Do not initiate dispute until the transaction is confirmed.",
        "customer_reply": "Thank you for reaching out. We see multiple transactions of 1000 BDT on that date. Could you share your brother's number so we can identify the right transaction? Please do not share your PIN or OTP with anyone.",
        "human_review_required": False,
        "confidence": 0.65,
        "reason_codes": [
            "ambiguous_match",
            "needs_clarification"
        ]
    },
    "TKT-009": {
        "ticket_id": "TKT-009",
        "relevant_transaction_id": "TXN-9901",
        "evidence_verdict": "consistent",
        "case_type": "merchant_settlement_delay",
        "severity": "medium",
        "department": "merchant_operations",
        "agent_summary": "Merchant reports yesterday's 15000 BDT settlement (TXN-9901) is delayed beyond the standard 11 AM next-day window. Settlement status is pending.",
        "recommended_next_action": "Route to merchant_operations to verify settlement batch status. If the batch is delayed, communicate a revised ETA to the merchant.",
        "customer_reply": "We have noted your concern about settlement TXN-9901. Our merchant operations team will check the batch status and update you on the expected settlement time through official channels.",
        "human_review_required": False,
        "confidence": 0.92,
        "reason_codes": [
            "merchant_settlement",
            "delay",
            "pending"
        ]
    },
    "TKT-010": {
        "ticket_id": "TKT-010",
        "relevant_transaction_id": "TXN-10002",
        "evidence_verdict": "consistent",
        "case_type": "duplicate_payment",
        "severity": "high",
        "department": "payments_ops",
        "agent_summary": "Customer reports duplicate electricity bill payment. Two identical 850 BDT payments to BILLER-DESCO were completed 12 seconds apart (TXN-10001 and TXN-10002). The second is likely the duplicate.",
        "recommended_next_action": "Verify the duplicate with payments_ops. If the biller confirms only one payment was received, initiate reversal of TXN-10002.",
        "customer_reply": "We have noted the possible duplicate payment for transaction TXN-10002. Our payments team will verify with the biller and any eligible amount will be returned through official channels. Please do not share your PIN or OTP with anyone.",
        "human_review_required": True,
        "confidence": 0.93,
        "reason_codes": [
            "duplicate_payment",
            "biller_verification_required"
        ]
    }
}
