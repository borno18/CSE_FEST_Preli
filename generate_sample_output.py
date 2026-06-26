import json
from fastapi.testclient import TestClient
from app.main import app

def generate_sample():
    client = TestClient(app)
    
    # Input matching SAMPLE-01 from the public sample pack
    sample_input = {
        "ticket_id": "TKT-001",
        "complaint": "I sent 5000 taka to a wrong number around 2pm today. The number was supposed to be 01712345678 but I think I typed it wrong. The person isn't responding to my call. Please help me get my money back.",
        "language": "en",
        "channel": "in_app_chat",
        "user_type": "customer",
        "campaign_context": "boishakh_bonanza_day_1",
        "transaction_history": [
            {
                "transaction_id": "TXN-9101",
                "timestamp": "2026-04-14T14:08:22Z",
                "type": "transfer",
                "amount": 5000,
                "counterparty": "+8801719876543",
                "status": "completed"
            },
            {
                "transaction_id": "TXN-9087",
                "timestamp": "2026-04-13T18:12:00Z",
                "type": "cash_in",
                "amount": 10000,
                "counterparty": "AGENT-512",
                "status": "completed"
            }
        ]
    }
    
    print("Sending POST request to /analyze-ticket...")
    response = client.post("/analyze-ticket", json=sample_input)
    
    if response.status_code == 200:
        output_data = response.json()
        print("Success! Writing output to sample_output.json...")
        with open("sample_output.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(json.dumps(output_data, indent=2, ensure_ascii=False))
    else:
        print(f"Error! HTTP {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    generate_sample()
