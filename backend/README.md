# ProtoRyde Phase 2 - Backend (Nervous System)

This is Anurup's Phase 2 Scope for the backend simulation and trigger engines.

## Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

## Running the Server
Make sure you are in the project root containing `backend/`.
```bash
uvicorn backend.main:app --reload --port 8000
```

## Features Implemented
- `GET /api/exclusions`: explicit exclusions list + version.
- `POST /api/policies/activate`: policy activation with exclusions acknowledgment gate.
- `POST /api/premium/predict`: zone-aware premium inference with adjustment breakdown.
- `GET /api/weather/current/{zone}`: normalized weather payload with simulated mode support.
- `GET /api/mock/delhivery/{zone}/{date}`: deterministic cancellation fixtures.
- `GET /api/mock/branches/{zone}`: deterministic branch-closure fixtures.
- `POST /api/triggers/simulate`: 4-layer fraud simulation returning timeline-ready output.
- `GET /api/policies/{rider_id}/current`: current active policy snapshot.
- `GET /api/policies/{rider_id}/history`: weekly policy history for rider timeline.
- `GET /api/policies/{rider_id}/current/document`: downloadable policy PDF with exclusions and thresholds.
- `GET /api/claims/{rider_id}`: rider claims history.
- `GET /api/claims`: admin claims list with optional filters (`zone`, `trigger_type`, `is_simulated`, `limit`).
- `APScheduler` (optional): 5-minute polling, enabled with `ENABLE_SCHEDULER=true`.
