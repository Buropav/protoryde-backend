# ProtoRyde Backend

Feature-complete backend repository for the hackathon.

## Structure
- `app/` -> active FastAPI backend
  - `api/` endpoints
  - `core/` database models + scheduler
  - `triggers/` weather + fraud + premium logic
  - `services/` ML+SHAP prediction, policy PDF generation, model training utility
  - `tests/` contract tests
- `main.py` -> root ASGI entrypoint (`app.main:app`)
- `requirements.txt` -> single dependency source

## Run
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## ML + PDF now integrated in active app
- ML status: `GET /api/premium/model-status`
- Premium prediction (ML-first with fallback): `POST /api/premium/predict`
- Policy PDF download: `GET /api/policies/{rider_id}/current/document`
- Optional local model training: `python app/services/train_model.py`

## Demo-Critical Endpoints
- `POST /api/demo/bootstrap`
- `POST /api/triggers/simulate`
- `GET /api/claims/{rider_id}`
- `GET /api/policies/{rider_id}/current`
- `GET /api/policies/{rider_id}/current/document`
