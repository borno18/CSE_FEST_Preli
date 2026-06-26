# RUNBOOK — QueueStorm Investigator

> For judges: this runbook lets you bring up the service from scratch in under 5 minutes using **only** Docker and an API key. No Python installation needed.

---

## Option A — Docker Hub (fastest, recommended)

### Prerequisites
- Docker Desktop installed and running
- A Google Gemini API key (free tier is sufficient)

### One-command start

```bash
docker run -p 8000:8000 -e GEMINI_API_KEY=<your_gemini_api_key> macloreniz/queuestorm:latest
```

### Verify it is running

```bash
# Health check (should return {"status":"ok"} within 60 seconds of start)
curl http://localhost:8000/health

# Swagger UI (interactive API explorer)
open http://localhost:8000/docs
```

### Send a test request

```bash
curl -X POST http://localhost:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "TKT-001",
    "complaint": "I sent 5000 taka to a wrong number around 2pm today. The number was supposed to be 01712345678 but I think I typed it wrong. The person is not responding. Please help.",
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
  }'
```

### Expected response shape

```json
{
  "ticket_id": "TKT-001",
  "relevant_transaction_id": "TXN-9101",
  "evidence_verdict": "consistent",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports sending 5000 BDT to +8801719876543 (TXN-9101) which they believe was the wrong recipient.",
  "recommended_next_action": "Verify TXN-9101 details and initiate the wrong-transfer dispute workflow.",
  "customer_reply": "We have noted your concern about TXN-9101. Our dispute team will review it through official channels.",
  "human_review_required": true,
  "confidence": 0.95,
  "reason_codes": ["wrong_transfer", "transaction_match"]
}
```

---

## Option B — Build from source (if you cannot pull from Docker Hub)

### Prerequisites
- Docker Desktop
- Git

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/borno18/CSE_FEST_Preli.git
cd CSE_FEST_Preli

# 2. Build the Docker image (takes ~2–3 minutes)
docker build -t queuestorm-local .

# 3. Run it with your Gemini API key
docker run -p 8000:8000 -e GEMINI_API_KEY=<your_gemini_api_key> queuestorm-local

# 4. Verify
curl http://localhost:8000/health
```

---

## Option C — Run without Docker (pure Python)

### Prerequisites
- Python 3.11 or 3.12
- pip

### Steps

```bash
# 1. Clone
git clone https://github.com/borno18/CSE_FEST_Preli.git
cd CSE_FEST_Preli

# 2. Create virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set the API key
#    Windows:
set GEMINI_API_KEY=<your_gemini_api_key>
#    Linux/macOS:
#    export GEMINI_API_KEY=<your_gemini_api_key>

# 5. Start the service
python run.py

# 6. Verify
curl http://localhost:8000/health
```

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | **Yes** | — | Google Gemini API key. Get one free at https://aistudio.google.com/app/apikey |
| `PORT` | No | `8000` | Port to bind the service on |
| `HIGH_VALUE_THRESHOLD` | No | `20000` | BDT amount above which human review is triggered |

> **Note on API key**: The Gemini free tier (gemini-2.5-flash) has a quota of 500 requests/day with no billing required. The service fails gracefully to a rules-based fallback if the Gemini API is unavailable — all endpoints remain functional.

---

## Port and binding

The service binds to `0.0.0.0:8000` by default. The Docker image exposes port `8000`. If you need a different port:

```bash
docker run -p 9000:8000 -e GEMINI_API_KEY=<key> macloreniz/queuestorm:latest
# Service is now at http://localhost:9000
```

---

## Running the test suite

```bash
# After cloning and installing dependencies (Option C steps 1-3)
python -m pytest -v
# Expected: 17 passed
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `{"detail":"missing ticket_id"}` | Ensure your JSON body includes `"ticket_id"` |
| `CRITICAL STARTUP ERROR: GEMINI_API_KEY is not set` | Pass `-e GEMINI_API_KEY=<key>` to docker run |
| Service times out on first request | The Gemini API can take 3–5s on first call. The service has a 12s timeout and falls back to rules if exceeded. |
| Port already in use | Change host port: `docker run -p 9000:8000 ...` |
| `docker: Error response from daemon: pull access denied` | Try Option B (build from source) |
