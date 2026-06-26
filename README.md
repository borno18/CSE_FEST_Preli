# QueueStorm Investigator — Team Antigravity

## Overview
**QueueStorm Investigator** is a high-performance, stateless backend AI/API service designed to serve as a copilot for human support agents during a high-volume promotional campaign. The service accepts a customer support ticket (including complaint text and recent transaction history) and returns a single structured JSON verdict. It performs deterministic transaction evidence-matching (determining whether customer claims align with transaction history ledger details), classifies/routes cases across 8 case types and 6 departments, and drafts safe, policy-compliant customer replies.

## Setup & Run
### Local
1. Clone the repository and navigate into the folder:
   ```bash
   cd CSE_FEST_Preli
   ```
2. Create a virtual environment and install the dependencies:
   ```bash
   python -m venv .venv
   Source-Folder: .venv\Scripts\activate   # On Windows
   # source .venv/bin/activate            # On macOS/Linux
   pip install -r requirements.txt
   ```
3. Create a `.env` file at the root of the project by copying `.env.example`:
   ```bash
   cp .env.example .env
   ```
   Fill in your `GEMINI_API_KEY` in the `.env` file.
4. Run the development server:
   ```bash
   python run.py
   ```
   The service will start at `http://localhost:8000`.
5. Run the test suite:
   ```bash
   python -m pytest
   ```

### Docker
1. Build the lightweight Docker image:
   ```bash
   docker build -t queuestorm-investigator .
   ```
2. Run the Docker container exposing port 8000:
   ```bash
   docker run -p 8000:8000 --env-file .env queuestorm-investigator
   ```

### Live deployment
Base URL: `https://your-deployed-service.com` (replace with your actual hosted endpoint)
- `GET  /health` - Immediate status verification
- `POST /analyze-ticket` - Perform evidence-matching and ticket triage

## Tech Stack
- **Language**: Python 3.11/3.12
- **Framework**: FastAPI (high-performance web framework)
- **Validation**: Pydantic v2 (enforces strict types, schema constraints, and enums)
- **AI SDK**: `google-genai` (modern Google GenAI Client SDK)
- **Testing**: `pytest` and `FastAPI TestClient`
- **Rate Limiting**: `slowapi` (IP-based limiters to protect API quotas)

## MODELS
| Model | Where it runs | Why chosen |
|---|---|---|
| `gemini-2.5-flash` | External Google Gemini API | Extremely low latency, cost-effective, supports Structured Outputs (JSON schema enforcement), and has strong multilingual/Banglish parsing capabilities. |

## AI / Reasoning Approach
The system uses a **Hybrid Rule + AI Architecture** that splits responsibilities logically to maximize reliability, safety, and correctness:
1. **Deterministic Request Parser**: Validates incoming schema, enforces required fields, and defensively filters out/skips malformed transaction entries rather than crashing.
2. **Deterministic Evidence Matcher (`app/matcher.py`)**: Runs a scoring algorithm matching the complaint's normalized text (converting Bengali digits to English digits and handling currency suffixes like "k") against transaction history amounts, counterparties, and types. It flags ties, handles duplicates (selecting the second/later transaction for `duplicate_payment`), and proposes an `evidence_verdict` (`consistent`, `inconsistent`, `insufficient_data`).
3. **Phishing Pre-Check Override**: Checks the complaint for critical phishing/impersonation markers (OTP, PIN, password, is-bKash queries, agent calls). If found, it immediately overrides all classification fields to safety values without invoking the LLM.
4. **LLM Analysis Layer (`app/classifier.py`)**: Passes the complaint and deterministic matcher findings (matched transaction ID and verdict) to the `gemini-2.5-flash` model. The LLM confirms classification, writes an agent summary, recommends a next action, and drafts a reply using **Structured Outputs** (JSON schema).
5. **Deterministic Fallback Path**: If the Gemini call times out (~8s ceiling) or fails (e.g. API down, rate limited), the service falls back to a rules-based classifier, ensuring it always returns a valid, schema-correct response within the 30-second budget.

## Safety Logic
Safety is enforced through a strict, independent **Post-Processing Safety Filter** in `app/rules.py` that runs on all outputs regardless of whether they came from the LLM or a fallback template:
1. **No Credentials Leak (Rule 1)**: `customer_reply` is scanned for credential keywords (`PIN`, `OTP`, `password`, `CVV`, `card number` runs). If a keyword is found, the filter checks for the presence of a safe warning pattern (e.g., "never share", "do not share"). If it is missing (implying the system is asking for credentials), the entire reply is substituted with a safe warning template.
2. **No Unauthorized Decisions (Rule 2)**: Both `customer_reply` and `recommended_next_action` are scanned for promise language ("we will refund you", "your money has been returned", "reversal has been processed"). If detected, the promise is discarded and replaced with: *"We have received your request. Any eligible amount will be returned through official channels after review."*
3. **No Unofficial Channels (Rule 3)**: Customer replies are scanned for mobile numbers. To prevent scammers from hijacking the reply to route customers to unofficial hotlines, the filter replaces any raw phone number with official support channel links: *"Please contact our official support hotline at 16247 or use the in-app support chat."*
4. **Prompt Injection Hardening (Rule 4)**: Complaint content is wrapped in clear system prompt delimiters and marked as untrusted user data. The model is instructed to treat it strictly as data to analyze, never as instructions to follow.

## Assumptions
- **HIGH_VALUE_THRESHOLD**: Set to `20,000` BDT. Transactions at or above this threshold trigger human review.
- **Severity Heuristic**:
  - `critical`: Phishing/social engineering, or high-value wrong transfer.
  - `high`: Confirmed money disputes (`wrong_transfer`, `duplicate_payment`, `agent_cash_in_issue`) at moderate/high amounts, or any case with `evidence_verdict: inconsistent`.
  - `medium`: Standard operational issues or merchant settlement delays.
  - `low`: Informational inquiries or low-value refund requests.
- **Refund vs. Payment Failed Disambiguation**: A refund request is classified as `refund_request` only if it represents a customer change-of-mind request. If the refund request stems from a transaction failure (e.g. balance deducted but payment failed), it is classified as `payment_failed` to isolate the root cause.
- **Phishing Priority**: If a complaint contains signals of both a wrong transfer and phishing (e.g., being tricked into transferring money by a fake agent), it is routed as `phishing_or_social_engineering` to `fraud_risk` because security risk outranks bookkeeping classification.

## Known Limitations
- **Multilingual Nuance**: Bengali slang or highly colloquial dialect text might sometimes fall back to the rules-based classifier if the LLM's confidence scores drop.
- **Strict Network Isolation**: The service depends on outbound HTTPS connection to Google Gemini API. If the environment blocks outbound calls, it will fall back to rules-based classification.

## Sample Request/Response
### Request
```json
{
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
```

### Response
```json
{
  "ticket_id": "TKT-001",
  "relevant_transaction_id": "TXN-9101",
  "evidence_verdict": "consistent",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports sending 5000 BDT via TXN-9101 to +8801719876543, which they now believe was the wrong recipient.",
  "recommended_next_action": "Verify TXN-9101 details with the customer and initiate the wrong-transfer dispute workflow per policy.",
  "customer_reply": "We have noted your concern about transaction TXN-9101. Please do not share your PIN or OTP with anyone. Our dispute team will review the case and contact you through official support channels.",
  "human_review_required": true,
  "confidence": 0.9,
  "reason_codes": [
    "wrong_transfer",
    "transaction_match",
    "dispute_initiated"
  ]
}
```
