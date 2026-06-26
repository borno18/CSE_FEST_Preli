import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """Verify health check endpoint returns 200 and ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_missing_ticket_id():
    """Verify missing ticket_id returns HTTP 400."""
    response = client.post("/analyze-ticket", json={
        "complaint": "I sent money to a wrong number."
    })
    assert response.status_code == 400
    assert "missing ticket_id" in response.json()["error"]

def test_empty_complaint():
    """Verify empty or whitespace-only complaint returns HTTP 422."""
    response = client.post("/analyze-ticket", json={
        "ticket_id": "TKT-001",
        "complaint": "   "
    })
    assert response.status_code == 422
    assert "complaint cannot be empty" in response.json()["error"]

def test_malformed_json_body():
    """Verify malformed JSON body returns HTTP 400."""
    # Test client allows sending raw data
    response = client.post(
        "/analyze-ticket",
        content="invalid json content here",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert "invalid JSON" in response.json()["error"]

def test_defensive_parsing_skips_bad_transactions():
    """Verify that malformed transaction history entries are skipped rather than crashing the request."""
    # We send one good transaction and one transaction with a string amount and one missing a status.
    # The API should parse the good transaction and skip the bad ones.
    # We will trigger the rules-fallback path to avoid real Gemini API calls during this test.
    # (By setting no GEMINI_API_KEY, it will fallback to rules-based processing).
    response = client.post("/analyze-ticket", json={
        "ticket_id": "TKT-TEST",
        "complaint": "I paid 500 BDT for bills.",
        "language": "en",
        "transaction_history": [
            {
                "transaction_id": "TXN-GOOD",
                "timestamp": "2026-04-14T14:00:00Z",
                "type": "payment",
                "amount": 500,
                "counterparty": "MERCHANT-A",
                "status": "completed"
            },
            {
                "transaction_id": "TXN-BAD-AMOUNT",
                "timestamp": "2026-04-14T14:00:00Z",
                "type": "payment",
                "amount": "not-a-number",
                "counterparty": "MERCHANT-B",
                "status": "completed"
            },
            {
                "transaction_id": "TXN-MISSING-FIELD",
                "timestamp": "2026-04-14T14:00:00Z",
                "type": "payment",
                "amount": 500,
                "counterparty": "MERCHANT-C"
                # status is missing
            }
        ]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["ticket_id"] == "TKT-TEST"
    assert data["relevant_transaction_id"] == "TXN-GOOD"  # correctly matched the good one
    assert data["evidence_verdict"] == "consistent"
