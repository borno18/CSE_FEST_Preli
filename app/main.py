import time
import copy
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.schemas import (
    AnalyzeTicketRequest,
    AnalyzeTicketResponse,
    TransactionHistoryEntry
)
from app.rules import (
    check_phishing_signals,
    clean_customer_reply,
    clean_recommended_action
)
from app.matcher import analyze_evidence
from app.classifier import classify_ticket_with_llm

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("queuestorm")

# Setup Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="QueueStorm Investigator API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configurations
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True if settings.FRONTEND_ORIGIN != "*" else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Lightweight health check endpoint responding immediately."""
    return {"status": "ok"}

def derive_department(case_type: str, complaint: str) -> str:
    """
    Derive the department name deterministically from the case type and complaint text.
    - wrong_transfer, contested refund_request -> dispute_resolution
    - payment_failed, duplicate_payment         -> payments_ops
    - phishing_or_social_engineering            -> fraud_risk
    - merchant_settlement_delay                 -> merchant_operations
    - agent_cash_in_issue                       -> agent_operations
    - refund_request (non-contested), other     -> customer_support
    """
    ct_lower = case_type.lower()
    comp_lower = complaint.lower()
    
    if ct_lower == "wrong_transfer":
        return "dispute_resolution"
    elif ct_lower in ("payment_failed", "duplicate_payment"):
        return "payments_ops"
    elif ct_lower == "phishing_or_social_engineering":
        return "fraud_risk"
    elif ct_lower == "merchant_settlement_delay":
        return "merchant_operations"
    elif ct_lower == "agent_cash_in_issue":
        return "agent_operations"
    elif ct_lower == "refund_request":
        dispute_keywords = ["contest", "dispute", "complain", "legal", "police", "court", "wrong", "cheat", "force", "lawyer", "scam", "fraud"]
        if any(kw in comp_lower for kw in dispute_keywords):
            return "dispute_resolution"
        return "customer_support"
    else:
        return "customer_support"

def check_human_review_required(
    case_type: str,
    evidence_verdict: str,
    relevant_transaction_id: Optional[str],
    amount_involved: float,
    high_value_threshold: float
) -> bool:
    """
    Determine if human review is required using a clean, deterministic rule.
    """
    if case_type == "phishing_or_social_engineering":
        return True
    if evidence_verdict == "inconsistent":
        return True
    if relevant_transaction_id is not None:
        if case_type in ["wrong_transfer", "duplicate_payment", "agent_cash_in_issue"]:
            return True
        if amount_involved >= high_value_threshold:
            return True
    return False

# Enums check to ensure output complies strictly with schemas
ALLOWED_CASE_TYPES = {
    'wrong_transfer', 'payment_failed', 'refund_request', 'duplicate_payment',
    'merchant_settlement_delay', 'agent_cash_in_issue', 'phishing_or_social_engineering', 'other'
}
ALLOWED_SEVERITIES = {'low', 'medium', 'high', 'critical'}

def _inline_schema(schema: dict) -> dict:
    """
    Resolve all $defs/$ref entries inline so that openapi_extra schemas
    can be embedded in the OpenAPI document without unresolvable $ref pointers.
    """
    schema = copy.deepcopy(schema)
    defs = schema.pop("$defs", {})

    def resolve(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref = obj["$ref"]
                if ref.startswith("#/$defs/"):
                    def_name = ref[len("#/$defs/"):]
                    if def_name in defs:
                        return resolve(copy.deepcopy(defs[def_name]))
            return {k: resolve(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [resolve(item) for item in obj]
        return obj

    return resolve(schema)

@app.post(
    "/analyze-ticket",
    response_model=AnalyzeTicketResponse,
    status_code=status.HTTP_200_OK,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": _inline_schema(AnalyzeTicketRequest.model_json_schema()),
                    "example": {
                        "ticket_id": "TKT-001",
                        "complaint": "I sent 5000 taka to a wrong number around 2pm today. I think I typed it wrong. Please help.",
                        "language": "en",
                        "channel": "in_app_chat",
                        "user_type": "customer",
                        "transaction_history": [
                            {
                                "transaction_id": "TXN-9101",
                                "timestamp": "2026-04-14T14:08:22Z",
                                "type": "transfer",
                                "amount": 5000,
                                "counterparty": "+8801719876543",
                                "status": "completed"
                            }
                        ]
                    }
                }
            }
        }
    }
)
@limiter.limit("10/second")
async def analyze_ticket(request: Request):
    """
    Main endpoint for analyzing a support ticket.
    Defensively parses payload, performs evidence matching, runs hybrid logic, and filters output.
    """
    start_time = time.perf_counter()
    
    # 1. Defensive Parsing
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON"})
        
    # Check ticket_id
    ticket_id = body.get("ticket_id")
    if ticket_id is None:
        return JSONResponse(status_code=400, content={"error": "missing ticket_id"})
    if not isinstance(ticket_id, str):
        return JSONResponse(status_code=400, content={"error": "ticket_id must be a string"})
        
    # Check complaint
    complaint = body.get("complaint")
    if complaint is None:
        return JSONResponse(status_code=400, content={"error": "missing complaint"})
    if not isinstance(complaint, str):
        return JSONResponse(status_code=400, content={"error": "complaint must be a string"})
        
    complaint_stripped = complaint.strip()
    if not complaint_stripped:
        return JSONResponse(status_code=422, content={"error": "complaint cannot be empty or contain only whitespace"})

    # Defensive parsing of transaction history: skip entries missing subfields or with wrong types
    clean_history: List[TransactionHistoryEntry] = []
    raw_history = body.get("transaction_history")
    
    # Standardize empty/null history
    if raw_history is not None and isinstance(raw_history, list):
        for entry in raw_history:
            if not isinstance(entry, dict):
                continue
            # Check required sub-fields
            required_subfields = ["transaction_id", "timestamp", "type", "amount", "counterparty", "status"]
            if not all(k in entry for k in required_subfields):
                continue  # skip entry missing sub-field
            # Coerce amount if possible
            try:
                entry["amount"] = float(entry["amount"])
            except (ValueError, TypeError):
                continue  # skip entry with bad amount type
            # Enforce enums
            if entry["type"] not in ["transfer", "payment", "cash_in", "cash_out", "settlement", "refund"]:
                continue
            if entry["status"] not in ["completed", "failed", "pending", "reversed"]:
                continue
            try:
                clean_history.append(TransactionHistoryEntry(**entry))
            except Exception:
                continue

    # Prepare input schemas/payloads
    lang = body.get("language")
    if lang not in ["en", "bn", "mixed"]:
        lang = "en"  # fallback default
        
    # 2. Phishing pre-check override (Rules Engine)
    phishing_override = check_phishing_signals(complaint_stripped)
    
    # 3. Deterministic Evidence Matcher
    relevant_tx_id, verdict, match_reasons = analyze_evidence(complaint_stripped, clean_history)
    
    # Find matched transaction amount if any
    matched_amount = 0.0
    if relevant_tx_id:
        for tx in clean_history:
            if tx.transaction_id == relevant_tx_id:
                matched_amount = tx.amount
                break

    # Initialize response defaults
    case_type = "other"
    severity = "low"
    agent_summary = "Classification fallback."
    recommended_next_action = "Review ticket."
    customer_reply = "We have received your ticket."
    confidence = 0.5
    reason_codes = ["rules_fallback"]
    
    if phishing_override:
        # Override fields
        case_type = "phishing_or_social_engineering"
        severity = "critical"
        agent_summary = "Pre-check detected potential phishing or credential safety risk."
        recommended_next_action = "Escalate to fraud_risk team immediately. Confirm to customer that the company never asks for OTP."
        if lang == "bn":
            customer_reply = "আপনার সুরক্ষার জন্য অনুগ্রহ করে কারো সাথে আপনার পিন (PIN) বা ওটিপি (OTP) শেয়ার করবেন না। কোনো সন্দেহজনক নম্বর থেকে কল আসলে আমাদের অফিসিয়াল হেল্পলাইন ১৬২৪৭ নম্বরে জানান।"
        else:
            customer_reply = "Thank you for reaching out before sharing any information. We never ask for your PIN, OTP, or password under any circumstances. Please do not share these with anyone."
        confidence = 1.0
        reason_codes = ["phishing_precheck_override"]
        relevant_tx_id = None
        verdict = "insufficient_data"
    else:
        # 4. Hybrid Classifier Flow
        try:
            # Format clean history list for LLM context
            history_dicts = [tx.model_dump() for tx in clean_history]
            
            # Request Gemini AI
            llm_result = await classify_ticket_with_llm(
                complaint=complaint_stripped,
                matched_txn_id=relevant_tx_id,
                verdict=verdict,
                history=history_dicts,
                language=lang
            )
            
            # Map LLM outputs — TEXT FIELDS ONLY
            llm_case_type = llm_result.get("case_type", "other")
            llm_severity = llm_result.get("severity", "low")
            
            # Ensure enums strictness
            if llm_case_type in ALLOWED_CASE_TYPES:
                case_type = llm_case_type
            if llm_severity in ALLOWED_SEVERITIES:
                severity = llm_severity
                
            agent_summary = llm_result.get("agent_summary", agent_summary)
            recommended_next_action = llm_result.get("recommended_next_action", recommended_next_action)
            customer_reply = llm_result.get("customer_reply", customer_reply)
            confidence = llm_result.get("confidence", 0.5)
            reason_codes = llm_result.get("reason_codes", ["llm_success"])
            
            # CRITICAL: evidence_verdict and relevant_transaction_id are
            # ALWAYS set by the deterministic matcher, never by the LLM.
            # The LLM only improves text quality (agent_summary, customer_reply).
            # This ensures the "investigator twist" is always authoritative.
            # (verdict and relevant_tx_id were already set above by analyze_evidence())

            
        except Exception as e:
            logger.warning(f"Failed to fetch or parse Gemini classification: {str(e)}. Using rules fallback.")
            # Deterministic Fallback Logic
            reason_codes = ["rules_fallback_due_to_error"]
            # Classify case_type using keywords + transaction history context
            comp_lower = complaint_stripped.lower()
            has_failed_tx = any(t.status == "failed" for t in clean_history)
            has_pending_tx = any(t.status == "pending" for t in clean_history)
            has_completed_transfers = any(
                t.type == "transfer" and t.status == "completed" for t in clean_history
            )
            has_cashin_tx = any(t.type == "cash_in" for t in clean_history)
            # Priority 1: Technical payment failure — tx status beats "refund" keyword in text
            if has_failed_tx and any(kw in comp_lower for kw in [
                "fail", "deduct", "balance", "recharge", "bill", "pay", "showed"
            ]):
                case_type = "payment_failed"
                severity = "high"
            # Priority 2: Explicit duplicate signals
            elif any(kw in comp_lower for kw in [
                "duplicate", "twice", "double", "deducted twice", "charged twice", "two times"
            ]):
                case_type = "duplicate_payment"
                severity = "high"
            # Priority 3: Specific wrong-transfer phrases (NOT bare "wrong" — too broad)
            elif any(kw in comp_lower for kw in [
                "wrong number", "wrong person", "wrong recipient", "wrong transfer",
                "typed wrong", "mistake", "stranger"
            ]):
                case_type = "wrong_transfer"
                severity = "high"
            # Priority 4: Transfer + completed tx where recipient didn't get it
            elif any(kw in comp_lower for kw in [
                "sent", "transfer", "didn't get", "did not get", "he says", "she says"
            ]) and has_completed_transfers:
                case_type = "wrong_transfer"
                severity = "high"
            # Priority 5: Refund request (only after payment_failed ruled out above)
            elif any(kw in comp_lower for kw in ["refund", "money back", "return"]):
                case_type = "refund_request"
                severity = "low"
            # Priority 6: Settlement delay
            elif any(kw in comp_lower for kw in ["settle", "settlement"]):
                case_type = "merchant_settlement_delay"
                severity = "medium"
            # Priority 7: Agent cash-in issue (check tx type + Bengali keywords)
            elif any(kw in comp_lower for kw in [
                "cash in", "deposit", "cash-in",
                "\u0995\u09cd\u09af\u09be\u09b6 \u0987\u09a8", "\u099c\u09ae\u09be", "\u098f\u099c\u09c7\u09a8\u09cd\u099f"
            ]) or (has_cashin_tx and any(kw in comp_lower for kw in [
                "agent", "balance", "\u09ac\u09cd\u09af\u09be\u09b2\u09c7\u09a8\u09cd\u09b8", "\u0986\u09b8\u09c7\u09a8\u09bf", "\u099f\u09be\u0995\u09be"
            ])):
                case_type = "agent_cash_in_issue"
                severity = "high"
            # Priority 8: Generic payment failure
            elif any(kw in comp_lower for kw in ["fail", "deduct", "failed"]) or has_failed_tx:
                case_type = "payment_failed"
                severity = "high"
            # Priority 9: Pending with no other match
            elif has_pending_tx:
                case_type = "payment_failed"
                severity = "medium"
            else:
                case_type = "other"
                severity = "low"
                
            # Build case-specific fallback details
            txn_ref = f" {relevant_tx_id}" if relevant_tx_id else ""
            
            # Agent Summary
            if case_type == "agent_cash_in_issue":
                agent_summary = f"[Fallback] Customer reports cash-in via{txn_ref} not reflected in balance. Transaction status is pending."
            elif case_type == "wrong_transfer":
                agent_summary = f"[Fallback] Customer reports sending money via{txn_ref} to the wrong recipient."
            elif case_type == "payment_failed":
                agent_summary = f"[Fallback] Customer reports payment failure via{txn_ref} with balance deducted."
            elif case_type == "duplicate_payment":
                agent_summary = f"[Fallback] Customer reports duplicate payment for transaction{txn_ref}."
            elif case_type == "merchant_settlement_delay":
                agent_summary = f"[Fallback] Merchant reports settlement delay for transaction{txn_ref}."
            elif case_type == "phishing_or_social_engineering":
                agent_summary = "[Fallback] Potential phishing or credential safety threat reported."
            elif case_type == "refund_request":
                agent_summary = f"[Fallback] Customer requests refund for transaction{txn_ref}."
            else:
                agent_summary = f"[Fallback] General support query{txn_ref}."

            # Recommended Action
            if case_type == "agent_cash_in_issue":
                recommended_next_action = f"Investigate pending cash-in status with agent operations for {relevant_tx_id or 'transaction'}."
            elif case_type == "wrong_transfer":
                recommended_next_action = f"Verify transaction details with customer and route to dispute resolution for wrong transfer workflow."
            elif case_type == "payment_failed":
                recommended_next_action = f"Investigate ledger status for failed payment {relevant_tx_id or ''}. Reversal if deducted."
            elif case_type == "duplicate_payment":
                recommended_next_action = f"Verify duplicate with payments team and biller/merchant for {relevant_tx_id or ''}."
            elif case_type == "merchant_settlement_delay":
                recommended_next_action = f"Route to merchant operations to verify settlement batch status."
            elif case_type == "phishing_or_social_engineering":
                recommended_next_action = f"Escalate to fraud risk team immediately. Log any reported number."
            elif case_type == "refund_request":
                recommended_next_action = f"Inform customer refund depends on merchant policy. Guide customer to merchant."
            else:
                recommended_next_action = f"Verify transaction and customer details and route to appropriate desk."

            # Customer Reply
            txn_str = f" {relevant_tx_id}" if relevant_tx_id else ""
            if lang == "bn":
                if case_type == "agent_cash_in_issue":
                    customer_reply = f"আপনার লেনদেন{txn_str} এর বিষয়ে আমরা অবগত হয়েছি। আমাদের এজেন্ট অপারেশন্স দল এটি দ্রুত যাচাই করবে এবং অফিসিয়াল চ্যানেলে আপনাকে জানাবে। অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।"
                elif case_type == "wrong_transfer":
                    customer_reply = f"আপনার লেনদেন{txn_str} এর বিষয়ে আমরা অবগত হয়েছি। আমাদের বিরোধ নিষ্পত্তি দল ভুল স্থানান্তরের কেসটি পর্যালোচনা করবে এবং অফিসিয়াল চ্যানেলে আপনার সাথে যোগাযোগ করবে। অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।"
                elif case_type == "payment_failed":
                    customer_reply = f"আমরা অবগত হয়েছি যে লেনদেন{txn_str} এর কারণে আপনার ব্যালেন্স কাটা হতে পারে। আমাদের পেমেন্ট টিম বিষয়টি পর্যালোচনা করবে এবং কোনো যোগ্য পরিমাণ অফিসিয়াল চ্যানেলে ফেরত দেওয়া হবে। অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।"
                elif case_type == "duplicate_payment":
                    customer_reply = f"আমরা লেনদেন{txn_str} এর জন্য সম্ভাব্য ডুপ্লিকেট পেমেন্টটি লক্ষ্য করেছি। আমাদের পেমেন্ট টিম এটি যাচাই করবে এবং কোনো যোগ্য পরিমাণ অফিসিয়াল চ্যানেলে ফেরত দেওয়া হবে। অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।"
                elif case_type == "merchant_settlement_delay":
                    customer_reply = f"সেটেলমেন্ট লেনদেন{txn_str} সংক্রান্ত আপনার অভিযোগটি আমরা পেয়েছি। আমাদের মার্চেন্ট অপারেশন্স দল এটি যাচাই করে আপনাকে অফিসিয়াল চ্যানেলে আপডেট জানাবে।"
                elif case_type == "phishing_or_social_engineering":
                    customer_reply = "আপনার সুরক্ষার জন্য অনুগ্রহ করে কারো সাথে আপনার পিন (PIN) বা ওটিপি (OTP) শেয়ার করবেন না। কোনো সন্দেহজনক নম্বর থেকে কল আসলে আমাদের অফিসিয়াল হেল্পলাইন ১৬২৪৭ নম্বরে জানান।"
                elif case_type == "refund_request":
                    customer_reply = "যোগাযোগ করার জন্য ধন্যবাদ। মার্চেন্ট পেমেন্টের রিফান্ড মার্চেন্টের নিজস্ব নীতির ওপর নির্ভর করে। আমরা মার্চেন্টের সাথে সরাসরি যোগাযোগ করার পরামর্শ দিচ্ছি। অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।"
                else:
                    customer_reply = "আমরা আপনার অভিযোগটি পেয়েছি এবং এটি তদন্ত করছি। অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।"
            else:
                if case_type == "agent_cash_in_issue":
                    customer_reply = f"We have noted your concern about cash-in transaction{txn_str}. Our agent operations team will verify the transaction status and update you. Please do not share your PIN or OTP with anyone."
                elif case_type == "wrong_transfer":
                    customer_reply = f"We have noted your concern about transaction{txn_str}. Our dispute team will review the wrong transfer case and contact you through official channels. Please do not share your PIN or OTP with anyone."
                elif case_type == "payment_failed":
                    customer_reply = f"We have noted that transaction{txn_str} may have caused an unexpected balance deduction. Our payments team will review the case and any eligible amount will be returned through official channels. Please do not share your PIN or OTP with anyone."
                elif case_type == "duplicate_payment":
                    customer_reply = f"We have noted the possible duplicate payment for transaction{txn_str}. Our payments team will verify with the biller and any eligible amount will be returned through official channels. Please do not share your PIN or OTP with anyone."
                elif case_type == "merchant_settlement_delay":
                    customer_reply = f"We have noted your concern about settlement{txn_str}. Our merchant operations team will check the batch status and update you on the expected settlement time through official channels."
                elif case_type == "phishing_or_social_engineering":
                    customer_reply = "Thank you for reaching out before sharing any information. We never ask for your PIN, OTP, or password under any circumstances. Please do not share these with anyone, even if they claim to be from us."
                elif case_type == "refund_request":
                    customer_reply = "Thank you for reaching out. Refunds for completed merchant payments depend on the merchant's own policy. We recommend contacting the merchant directly. Please do not share your PIN or OTP with anyone."
                else:
                    customer_reply = "We have received your ticket and are currently reviewing the details. Please do not share your PIN or OTP with anyone."
            confidence = 0.5

    # 5. Derive department
    department = derive_department(case_type, complaint_stripped)
    
    # 6. Post-processing safety filters
    customer_reply = clean_customer_reply(customer_reply, case_type, lang)
    recommended_next_action = clean_recommended_action(recommended_next_action)
    
    # 7. human_review_required calculation
    human_review = check_human_review_required(
        case_type=case_type,
        evidence_verdict=verdict,
        relevant_transaction_id=relevant_tx_id,
        amount_involved=matched_amount,
        high_value_threshold=settings.HIGH_VALUE_THRESHOLD
    )
    
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    
    # Log triage result without raw message content to keep logs safe
    logger.info(
        f"TriageResult: ticket_id={ticket_id} case_type={case_type} severity={severity} "
        f"evidence_verdict={verdict} relevant_transaction_id={relevant_tx_id} "
        f"department={department} human_review={human_review} latency_ms={latency_ms}"
    )
    
    return AnalyzeTicketResponse(
        ticket_id=ticket_id,
        relevant_transaction_id=relevant_tx_id,
        evidence_verdict=verdict,
        case_type=case_type,
        severity=severity,
        department=department,
        agent_summary=agent_summary,
        recommended_next_action=recommended_next_action,
        customer_reply=customer_reply,
        human_review_required=human_review,
        confidence=confidence,
        reason_codes=reason_codes
    )
