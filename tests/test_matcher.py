import pytest
from app.matcher import extract_amounts, match_counterparty, analyze_evidence
from app.schemas import TransactionHistoryEntry

def test_extract_amounts_english():
    """Verify BDT amounts are correctly extracted from English texts."""
    assert 5000.0 in extract_amounts("I sent 5000 BDT to my friend.")
    assert 5000.0 in extract_amounts("I sent 5k to a number.")
    assert 15000.0 in extract_amounts("Please check my settlement of 15k BDT.")
    assert 1200.0 in extract_amounts("My balance had 1200 taka deducted.")

def test_extract_amounts_bengali():
    """Verify BDT amounts are correctly extracted from Bengali texts."""
    assert 2000.0 in extract_amounts("আমি ২০০০ টাকা ক্যাশ ইন করেছি।")
    assert 500.0 in extract_amounts("আমার ৫০০ টাকা কেটেছে।")
    assert 850.0 in extract_amounts("বিদ্যুৎ বিল ৮৫০ টাকা পরিশোধ করেছি।")

def test_match_counterparty_phone():
    """Verify fuzzy matching for phone number counterparties."""
    assert match_counterparty("+8801719876543", "Sent money to 01719876543 by mistake") is True
    assert match_counterparty("+8801719876543", "The number is 1719876543") is True
    assert match_counterparty("+8801719876543", "Sent to 01812345678 instead") is False

def test_match_counterparty_name():
    """Verify fuzzy matching for merchant or agent names."""
    assert match_counterparty("MERCHANT-MOBILE-OP", "I paid mobile-op for recharge") is True
    assert match_counterparty("BILLER-DESCO", "Desco bill payment was twice") is True
    assert match_counterparty("AGENT-318", "deposited at agent 318") is True

def test_analyze_evidence_duplicate_payment():
    """Verify duplicate payment matching selects the second transaction (later timestamp)."""
    history = [
        TransactionHistoryEntry(
            transaction_id="TXN-D1",
            timestamp="2026-04-14T08:15:30Z",
            type="payment",
            amount=850.0,
            counterparty="BILLER-DESCO",
            status="completed"
        ),
        TransactionHistoryEntry(
            transaction_id="TXN-D2",
            timestamp="2026-04-14T08:15:42Z",
            type="payment",
            amount=850.0,
            counterparty="BILLER-DESCO",
            status="completed"
        )
    ]
    complaint = "I paid 850 BDT to Desco but it deducted twice."
    rel_id, verdict, reasons = analyze_evidence(complaint, history)
    assert rel_id == "TXN-D2"  # points to the duplicate (second one)
    assert verdict == "consistent"

def test_analyze_evidence_ambiguous_tie():
    """Verify multiple completed transfers of the same amount to different counterparties results in insufficient_data."""
    history = [
        TransactionHistoryEntry(
            transaction_id="TXN-1",
            timestamp="2026-04-13T11:20:00Z",
            type="transfer",
            amount=1000.0,
            counterparty="+8801712001122",
            status="completed"
        ),
        TransactionHistoryEntry(
            transaction_id="TXN-2",
            timestamp="2026-04-13T19:45:00Z",
            type="transfer",
            amount=1000.0,
            counterparty="+8801812334455",
            status="completed"
        )
    ]
    complaint = "I sent 1000 to my brother yesterday but he says he didn't get it."
    rel_id, verdict, reasons = analyze_evidence(complaint, history)
    assert rel_id is None
    assert verdict == "insufficient_data"
    assert "ambiguous_multiple_matches" in reasons

def test_analyze_evidence_established_recipient_inconsistent():
    """Verify wrong transfer claims are inconsistent if prior completed transactions to the recipient exist."""
    history = [
        TransactionHistoryEntry(
            transaction_id="TXN-RECENT",
            timestamp="2026-04-14T11:30:00Z",
            type="transfer",
            amount=2000.0,
            counterparty="+8801812345678",
            status="completed"
        ),
        TransactionHistoryEntry(
            transaction_id="TXN-PRIOR-1",
            timestamp="2026-04-10T09:15:00Z",
            type="transfer",
            amount=2500.0,
            counterparty="+8801812345678",
            status="completed"
        ),
        TransactionHistoryEntry(
            transaction_id="TXN-PRIOR-2",
            timestamp="2026-04-05T17:45:00Z",
            type="transfer",
            amount=1500.0,
            counterparty="+8801812345678",
            status="completed"
        )
    ]
    complaint = "I sent 2000 BDT to wrong person. Please reverse."
    rel_id, verdict, reasons = analyze_evidence(complaint, history)
    assert rel_id == "TXN-RECENT"
    assert verdict == "inconsistent"
    assert "established_recipient_pattern" in reasons
