"""
Validate QueueStorm Investigator against all 10 public sample cases.
Uses FastAPI TestClient — no running server required.
Prints a comparison table and PASS/FAIL per case.
"""
import json
import sys
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SAMPLE_CASES_PATH = r"C:\Users\joydi\Downloads\SUST_Preli_Sample_Cases.json"

def validate():
    with open(SAMPLE_CASES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    
    cases = data["cases"]
    total = len(cases)
    passed = 0
    failed_details = []

    print(f"\n{'='*80}")
    print(f"QueueStorm Investigator — Public Sample Validation ({total} cases)")
    print(f"{'='*80}\n")

    for case in cases:
        cid = case["id"]
        label = case["label"]
        inp = case["input"]
        expected = case["expected_output"]

        response = client.post("/analyze-ticket", json=inp)
        
        if response.status_code != 200:
            print(f"[FAIL] {cid} ({label}) — HTTP {response.status_code}")
            failed_details.append(f"{cid}: HTTP error {response.status_code}")
            continue

        actual = response.json()
        
        # Key fields that must match
        checks = {
            "ticket_id":              actual.get("ticket_id") == expected.get("ticket_id"),
            "relevant_transaction_id": actual.get("relevant_transaction_id") == expected.get("relevant_transaction_id"),
            "evidence_verdict":        actual.get("evidence_verdict") == expected.get("evidence_verdict"),
            "case_type":               actual.get("case_type") == expected.get("case_type"),
            "department":              actual.get("department") == expected.get("department"),
            "human_review_required":   actual.get("human_review_required") == expected.get("human_review_required"),
        }
        
        all_pass = all(checks.values())
        status = "PASS" if all_pass else "FAIL"
        if all_pass:
            passed += 1

        print(f"[{status}] {cid} — {label}")
        for field, ok in checks.items():
            icon = "OK" if ok else "XX"
            exp_val = expected.get(field)
            act_val = actual.get(field)
            if not ok:
                print(f"       [{icon}] {field}: expected={exp_val!r}  got={act_val!r}")
        if all_pass:
            print(f"       All 6 key fields match OK  |  severity={actual['severity']}  confidence={actual.get('confidence', 0.0):.2f}")
        print()

    print(f"{'='*80}")
    print(f"RESULT: {passed}/{total} sample cases fully matched")
    print(f"{'='*80}\n")
    return passed, total

if __name__ == "__main__":
    passed, total = validate()
    sys.exit(0 if passed == total else 1)
