# ProtoRyde Backend

Consolidated backend repository for the hackathon.

## Structure
- `app/` -> active FastAPI backend (API routes, trigger engine, persistence, tests)
- `legacy/` -> preserved earlier backend implementation (reference only)
- `main.py` -> root ASGI entrypoint (`app.main:app`)
- `requirements.txt` -> single dependency source for this repo

## Run
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Demo-Critical Endpoints
- `POST /api/demo/bootstrap`
- `POST /api/triggers/simulate`
- `GET /api/claims/{rider_id}`
- `GET /api/policies/{rider_id}/current`
- `GET /api/policies/{rider_id}/current/document`
