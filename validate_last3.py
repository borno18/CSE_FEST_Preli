"""Quick validation for TKT-008, 009, 010 only."""
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

with open(r"C:\Users\joydi\Downloads\SUST_Preli_Sample_Cases.json", encoding="utf-8") as f:
    cases = json.load(f)["cases"]

CHECKS = ["ticket_id", "relevant_transaction_id", "evidence_verdict", "case_type", "department", "human_review_required"]

for case in cases[7:]:  # TKT-008, 009, 010
    cid = case["id"]
    expected = case["expected_output"]
    resp = client.post("/analyze-ticket", json=case["input"])
    actual = resp.json()
    
    all_ok = all(actual.get(f) == expected.get(f) for f in CHECKS)
    status = "PASS" if all_ok else "FAIL"
    print(f"[{status}] {cid} - {case['label']}")
    for f in CHECKS:
        ev, av = expected.get(f), actual.get(f)
        icon = "OK" if ev == av else "XX"
        if ev != av:
            print(f"   [{icon}] {f}: expected={ev!r} got={av!r}")
    print(f"   severity={actual.get('severity')}  confidence={actual.get('confidence', 0):.2f}\n")
