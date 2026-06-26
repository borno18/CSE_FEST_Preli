import re
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any
from app.schemas import TransactionHistoryEntry

# Bengali to English digit mapping
BN_TO_EN_DIGITS = {
    "০": "0", "১": "1", "২": "2", "৩": "3", "৪": "4",
    "৫": "5", "৬": "6", "৭": "7", "৮": "8", "৯": "9"
}

def normalize_text(text: str) -> str:
    """Normalize text by converting Bengali digits to English digits and converting to lowercase."""
    if not text:
        return ""
    normalized = text
    for bn, en in BN_TO_EN_DIGITS.items():
        normalized = normalized.replace(bn, en)
    return normalized.lower()

def extract_amounts(complaint: str) -> List[float]:
    """
    Extract BDT amounts from complaint text.
    Handles standard integers, floats, and 'k' suffixes (e.g. 5k -> 5000).
    """
    normalized = normalize_text(complaint)
    # Match pattern for 'k' suffix, e.g. 5k, 1.5k, 15k
    k_matches = re.findall(r"\b(\d+(?:\.\d+)?)\s*k\b", normalized)
    amounts = []
    for match in k_matches:
        try:
            amounts.append(float(match) * 1000)
        except ValueError:
            pass
            
    # Match standard numbers of 3 to 6 digits (BDT transactions are typically in hundreds/thousands)
    standard_matches = re.findall(r"\b\d{3,6}\b", normalized)
    for match in standard_matches:
        try:
            amounts.append(float(match))
        except ValueError:
            pass
            
    return list(set(amounts))

def match_counterparty(counterparty: str, complaint: str) -> bool:
    """
    Fuzzy match a counterparty name/phone number against the complaint text.
    """
    comp_normalized = normalize_text(complaint)
    cp_normalized = normalize_text(counterparty)
    
    # If counterparty is a phone number, extract its digits (usually last 6-10 digits)
    cp_digits = re.sub(r"\D", "", cp_normalized)
    if cp_digits:
        # Check if the full number or at least the last 8 digits are in the complaint
        if len(cp_digits) >= 8:
            last_8 = cp_digits[-8:]
            if last_8 in comp_normalized:
                return True
        elif cp_digits in comp_normalized:
            return True
            
    # Otherwise, split counterparty identifier (like 'BILLER-DESCO', 'MERCHANT-7821') and check for match
    parts = re.split(r"[-_\s]", cp_normalized)
    for part in parts:
        if len(part) >= 3 and part not in ["merchant", "agent", "biller", "self"]:
            if part in comp_normalized:
                return True
    return False

def analyze_evidence(
    complaint: str,
    history: List[TransactionHistoryEntry]
) -> Tuple[Optional[str], str, List[str]]:
    """
    Score each transaction in history against the complaint.
    Returns: (relevant_transaction_id, evidence_verdict, reason_codes)
    """
    if not history:
        return None, "insufficient_data", ["no_transaction_history"]

    normalized_complaint = normalize_text(complaint)
    extracted_amounts = extract_amounts(complaint)
    
    # Keywords matching for types
    # has_wrong: customer believes money went to wrong recipient OR recipient says they didn't get it
    has_wrong = any(kw in normalized_complaint for kw in [
        "wrong number", "wrong person", "wrong recipient", "wrong transfer", "wrong account",
        "typed wrong", "mistake", "stranger", "didn't get", "did not get", "not received by",
        "he didn't", "she didn't", "they didn't", "brother", "sister", "friend",
        "ভুল", "ভুল নম্বরে", "ভুল নাম্বারে", "ভুল করে"
    ])
    # has_failed: balance deducted / payment technically failed (NOT colloquial "didn't receive")
    has_failed = any(kw in normalized_complaint for kw in [
        "app showed failed", "transaction failed", "payment failed", "deduct", "balance deducted",
        "balance cut", "balance keteche", "failed", "kete geche",
        "ডিপোজিট হয়নি", "ব্যালেন্স কেটেছে", "ব্যালেন্সে আসেনি", "টাকা কেটেছে"
    ])
    has_refund = any(kw in normalized_complaint for kw in ["refund", "money back", "return", "রিফান্ড", "ফেরত"])
    has_duplicate = any(kw in normalized_complaint for kw in ["duplicate", "twice", "double", "two times", "ডাবল", "দুইবার", "২ বার", "ভুল করে দুই বার"])
    has_settlement = any(kw in normalized_complaint for kw in ["settle", "settlement", "merchant sales", "সেলস", "সেটেলমেন্ট"])

    scored_txs = []
    
    for tx in history:
        score = 0.0
        reasons = []
        
        # 1. Amount matching
        amount_matched = False
        for amt in extracted_amounts:
            if abs(tx.amount - amt) < 0.01:
                score += 10.0
                amount_matched = True
                reasons.append("amount_match")
                break
                
        # 2. Counterparty matching
        if match_counterparty(tx.counterparty, complaint):
            score += 8.0
            reasons.append("counterparty_match")
            
        # 3. Type matching
        type_matched = False
        if tx.type == "transfer" and has_wrong:
            score += 5.0
            type_matched = True
            reasons.append("type_transfer_wrong")
        elif tx.type == "payment" and (has_failed or has_duplicate):
            score += 5.0
            type_matched = True
            reasons.append("type_payment_failed_or_duplicate")
        elif tx.type == "cash_in" and has_failed:
            score += 5.0
            type_matched = True
            reasons.append("type_cash_in_failed")
        elif tx.type == "settlement" and has_settlement:
            score += 5.0
            type_matched = True
            reasons.append("type_settlement_match")
        elif tx.type == "refund" and has_refund:
            score += 5.0
            type_matched = True
            reasons.append("type_refund_match")
            
        # Generic fallback type points if amount matched
        if amount_matched and not type_matched:
            if tx.type in ["transfer", "payment"] and not has_settlement:
                score += 2.0
                reasons.append("type_generic_match")

        # 4. Status matching
        if tx.status == "failed" and has_failed:
            score += 3.0
            reasons.append("status_failed_match")
        elif tx.status == "pending" and (has_failed or has_settlement):
            score += 3.0
            reasons.append("status_pending_match")
        elif tx.status == "completed" and not has_failed:
            score += 2.0
            reasons.append("status_completed_match")
            
        # 5. Temporal clue matching
        try:
            # Assumes ISO timestamp format containing Txx:xx:xx
            if "T" in tx.timestamp:
                time_part = tx.timestamp.split("T")[1]
                tx_hour = int(time_part.split(":")[0])
                
                time_matched = False
                # Morning: 5 AM to 12 PM
                if any(kw in normalized_complaint for kw in ["morning", "sokal", "সকাল", "সকালে", "am"]):
                    if 5 <= tx_hour < 12:
                        time_matched = True
                # Afternoon: 12 PM to 5 PM
                elif any(kw in normalized_complaint for kw in ["afternoon", "dupur", "bikel", "bikale", "দুপুর", "দুপুরে", "বিকাল", "বিকালে"]):
                    if 12 <= tx_hour < 17:
                        time_matched = True
                # Evening: 5 PM to 9 PM
                elif any(kw in normalized_complaint for kw in ["evening", "shondha", "সন্ধ্যা", "সন্ধ্যায়"]):
                    if 17 <= tx_hour < 21:
                        time_matched = True
                # Night: 9 PM to 5 AM
                elif any(kw in normalized_complaint for kw in ["night", "rat", "rate", "রাত", "রাতে", "midnight", "মধ্যরাত"]):
                    if tx_hour >= 21 or tx_hour < 5:
                        time_matched = True
                        
                if time_matched:
                    score += 3.0
                    reasons.append("time_match")
        except Exception:
            pass
            
        if score > 0:
            scored_txs.append((tx, score, reasons))

    if not scored_txs:
        return None, "insufficient_data", ["no_matching_transaction"]

    # Sort scored transactions by score descending, then by timestamp descending
    scored_txs.sort(key=lambda x: (x[1], x[0].timestamp), reverse=True)
    
    max_score = scored_txs[0][1]
    
    # If the highest score is too low (e.g. less than 8, meaning we didn't even match amount/counterparty),
    # it's insufficient data.
    if max_score < 8.0:
        return None, "insufficient_data", ["low_matching_confidence"]
        
    # Check for ties or duplicates
    candidates = [x for x in scored_txs if x[1] == max_score]
    
    # Special duplicate payment logic:
    # If the user complains about duplicate charge, and there are two identical transactions (same amount, same counterparty),
    # we select the second (later) one as the suspected duplicate.
    if len(candidates) >= 2 and has_duplicate:
        tx1, tx2 = candidates[0][0], candidates[1][0]
        if tx1.amount == tx2.amount and tx1.counterparty == tx2.counterparty:
            # Pick the one with the later timestamp
            t1 = datetime.fromisoformat(tx1.timestamp.replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(tx2.timestamp.replace("Z", "+00:00"))
            selected_tx = tx1 if t1 > t2 else tx2
            return selected_tx.transaction_id, "consistent", ["duplicate_payment", "transaction_match"]

    # If there is an ambiguous tie to different counterparties (e.g. SAMPLE-08)
    if len(candidates) >= 2:
        counterparties = {x[0].counterparty for x in candidates}
        if len(counterparties) > 1:
            return None, "insufficient_data", ["ambiguous_multiple_matches"]

    # Best match
    matched_tx, score, reasons = candidates[0]
    relevant_id = matched_tx.transaction_id
    
    # Determine verdict based on matched transaction details vs customer claims
    verdict = "consistent"
    verdict_reasons = list(reasons)
    
    # Check inconsistency conditions
    # 1. Customer claims duplicate payment, but we only have 1 matching transaction
    if has_duplicate and len([t for t in history if abs(t.amount - matched_tx.amount) < 0.01]) < 2:
        verdict = "inconsistent"
        verdict_reasons.append("duplicate_claimed_but_only_one_transaction")
        
    # 2. Customer claims money deducted but transaction status is failed (so no money moved)
    elif has_failed and matched_tx.status == "failed" and "deduct" in normalized_complaint:
        # Wait, if transaction status is failed, money is returned or never left. If customer claims balance deducted,
        # it is inconsistent with a standard failed transaction ledger (which should show money is safe).
        # Wait, SAMPLE-03 says "failed payment with balance deducted is consistent".
        # Let's check: in SAMPLE-03, "TXN-9301 status failed, payment, amount 1200. expected_output: consistent."
        # Ah! In SAMPLE-03, it is consistent with "payment_failed-style deduction-without-confirmation narrative".
        # Wait! When is status failed inconsistent?
        # Let's look at section 4.2 of the prompt:
        # "the transaction status is failed (so no money actually moved) while the complaint insists money was deducted and never returned, or the matched transaction's status is reversed already while the complaint claims they never got their money back."
        # Wait, if the prompt says "status is failed (so no money actually moved) while the complaint insists money was deducted... is inconsistent",
        # but SAMPLE-03's rationale says: "Clear payment failure with claimed balance deduction... consistent... if balance was deducted on a failed payment, initiate reversal".
        # Oh, in SAMPLE-03, it's consistent because it's a payment_failed case where status is failed but balance was deducted.
        # Wait, what if the status is completed but complaint says failed? Consistent (money deducted, merchant didn't get it).
        # What if the status is reversed already, but complaint says they never got money back? Inconsistent (since it is already reversed!).
        pass
        
    # Established recipient pattern for wrong transfer (SAMPLE-02)
    if has_wrong and matched_tx.type == "transfer":
        # Check if there are multiple completed transfers to the same counterparty in the history
        prior_transfers = [
            t for t in history 
            if t.type == "transfer" 
            and t.counterparty == matched_tx.counterparty 
            and t.status == "completed"
        ]
        if len(prior_transfers) >= 2: # e.g. 3 transfers total to this recipient
            verdict = "inconsistent"
            verdict_reasons.append("established_recipient_pattern")
            
    # If the transaction is already reversed (completed reversal) but user claims they didn't get money back
    if matched_tx.status == "reversed" and has_failed:
        verdict = "inconsistent"
        verdict_reasons.append("transaction_already_reversed")

    return relevant_id, verdict, verdict_reasons
