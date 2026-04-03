# ProtoRyde Backend Runbook (Backend Owner)

This runbook is for deterministic demo setup and teammate handoff.

## 1) Start Backend
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Health check:
```bash
curl -s http://127.0.0.1:8000/health
```

## 2) Critical Demo Sequence (copy-paste)

### Step A: Bootstrap rider + policy
```bash
curl -s -X POST http://127.0.0.1:8000/api/demo/bootstrap \
  -H "Content-Type: application/json" \
  -d '{
    "rider_id":"rdr_demo_hsr",
    "rider_name":"Pranav",
    "zone":"HSR Layout",
    "upi_id":"pranav@okicici",
    "exclusions_accepted": true
  }'
```

### Step B: Simulate heavy rain trigger
```bash
curl -s -X POST http://127.0.0.1:8000/api/triggers/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "zone":"HSR Layout",
    "trigger_type":"HEAVY_RAIN",
    "is_simulated": true,
    "rider_id":"rdr_demo_hsr"
  }'
```

### Step C: Fetch claims timeline data
```bash
curl -s http://127.0.0.1:8000/api/claims/rdr_demo_hsr
```

### Step D: Fetch current policy
```bash
curl -s http://127.0.0.1:8000/api/policies/rdr_demo_hsr/current
```

### Step E: Download policy PDF
```bash
curl -L http://127.0.0.1:8000/api/policies/rdr_demo_hsr/current/document -o policy.pdf
```

## 3) Error Codes Frontend Must Handle
- `UNSUPPORTED_ZONE` (422)
- `UNSUPPORTED_TRIGGER` (422)
- `EXCLUSIONS_NOT_ACKNOWLEDGED` (422)
- `POLICY_NOT_FOUND` (404)
- `RIDER_NOT_FOUND` (404)
- `ZONE_NOT_FOUND` (404)

## 4) Tests
Run lightweight contract tests:
```bash
python3 -m unittest app.tests.test_phase2_contracts -v
```

Run endpoint-level reliability tests:
```bash
python3 -m unittest app.tests.test_api_endpoints -v
```

## 5) Notes
- `POST /api/premium/predict` is ML-first (`engine=ml_shap`) when `model.pkl` is available.
- If ML model is missing, backend falls back to rule engine (`engine=rule_engine`) and stays demo-safe.
- Frontend must consume fixed fraud layer order from API.
