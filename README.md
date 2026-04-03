# ProtoRyde Backend

This repository now contains the consolidated backend used for the hackathon demo.

## Layout
- `backend/`: current API, trigger engine, simulation flow, policy/claims persistence, PDF document endpoint
- `legacy_v1/`: preserved earlier backend modules (`ml_service.py`, `pdf_service.py`, `train.py`, etc.)
- `main.py`: root ASGI entrypoint proxying to `backend.main:app`

## Run
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Critical Endpoints
- `POST /api/demo/bootstrap`
- `POST /api/triggers/simulate`
- `GET /api/claims/{rider_id}`
- `GET /api/policies/{rider_id}/current`
- `GET /api/policies/{rider_id}/current/document`
