from typing import Optional, Literal, Any, Dict, List
from pydantic import BaseModel, Field

# Transaction History Entry Schema
class TransactionHistoryEntry(BaseModel):
    transaction_id: str
    timestamp: str  # ISO 8601
    type: Literal['transfer', 'payment', 'cash_in', 'cash_out', 'settlement', 'refund']
    amount: float
    counterparty: str
    status: Literal['completed', 'failed', 'pending', 'reversed']

# Input Request Schema for POST /analyze-ticket
class AnalyzeTicketRequest(BaseModel):
    ticket_id: str
    complaint: str
    language: Optional[Literal['en', 'bn', 'mixed']] = None
    channel: Optional[Literal['in_app_chat', 'call_center', 'email', 'merchant_portal', 'field_agent']] = None
    user_type: Optional[Literal['customer', 'merchant', 'agent', 'unknown']] = None
    campaign_context: Optional[str] = None
    transaction_history: Optional[List[TransactionHistoryEntry]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None

# Structured Output Schema for Gemini AI
class LLMAnalysis(BaseModel):
    case_type: Literal[
        'wrong_transfer',
        'payment_failed',
        'refund_request',
        'duplicate_payment',
        'merchant_settlement_delay',
        'agent_cash_in_issue',
        'phishing_or_social_engineering',
        'other'
    ]
    severity: Literal['low', 'medium', 'high', 'critical']
    agent_summary: str
    recommended_next_action: str
    customer_reply: str
    confidence: float
    reason_codes: List[str]

# API Response Schema for POST /analyze-ticket
class AnalyzeTicketResponse(BaseModel):
    ticket_id: str
    relevant_transaction_id: Optional[str] = None
    evidence_verdict: Literal['consistent', 'inconsistent', 'insufficient_data']
    case_type: Literal[
        'wrong_transfer',
        'payment_failed',
        'refund_request',
        'duplicate_payment',
        'merchant_settlement_delay',
        'agent_cash_in_issue',
        'phishing_or_social_engineering',
        'other'
    ]
    severity: Literal['low', 'medium', 'high', 'critical']
    department: Literal[
        'customer_support',
        'dispute_resolution',
        'payments_ops',
        'merchant_operations',
        'agent_operations',
        'fraud_risk'
    ]
    agent_summary: str
    recommended_next_action: str
    customer_reply: str
    human_review_required: bool
    confidence: float
    reason_codes: List[str]
