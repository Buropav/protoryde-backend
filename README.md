# ProtoRyde Backend

Feature-complete backend repository for the hackathon.

## Structure
- `app/` -> active FastAPI backend
  - `api/` endpoints
  - `core/` database models + scheduler
  - `triggers/` weather + fraud trigger logic
  - `services/` pricing, ML+SHAP prediction, PDF generation, model training utility
  - `tests/` contract tests
- `docs/API_CONTRACT.md` -> frontend/backend integration contract
- `docs/BACKEND_RUNBOOK.md` -> backend owner runbook + curl payloads + error handling
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
- Forecast: `GET /api/forecast/{zone}` (Prophet-first, fallback when Prophet unavailable)
- Model monitoring summary: `GET /api/admin/model-monitoring`
- Resolve actual outcome for a prediction: `POST /api/admin/model-monitoring/resolve`
- Retrain all models immediately: `POST /api/admin/model-retrain`

## Demo-Critical Endpoints
- `POST /api/demo/bootstrap`
- `POST /api/triggers/simulate`
- `GET /api/claims/{rider_id}`
- `GET /api/policies/{rider_id}/current`
- `GET /api/policies/{rider_id}/current/document`

## Reliability Tests
```bash
python3 -m unittest app.tests.test_phase2_contracts -v
python3 -m unittest app.tests.test_api_endpoints -v
```

## Deploy on Render

This repo includes `render.yaml` and `Procfile` for Render deployment.

1. Create a **Blueprint** service in Render and point it to this repository.
2. Set service root to `protoryde-backend` if deploying from the umbrella repo.
3. Render provisions `protoryde-db` from `render.yaml` and injects `DATABASE_URL`.
4. Keep `ENABLE_SCHEDULER=false` in production unless you intentionally want live polling.

### Beginner flow (recommended)
1. Run preflight locally:
   ```bash
   ./scripts/render_preflight.sh
   ```
2. Deploy from Render Blueprint.
3. Run live smoke checks against Render URL:
   ```bash
   BACKEND_URL=https://<your-service>.onrender.com ./scripts/render_live_smoke.sh
   ```

See full guide: `docs/RENDER_FIRST_DEPLOY.md`

### Notes
- The app normalizes `postgres://` to `postgresql://` automatically for SQLAlchemy compatibility.
- `model.pkl` is optional; premium prediction falls back to the rule engine when the model is absent.
- Scheduled retraining is optional and controlled by `ENABLE_ML_RETRAIN` and `ML_RETRAIN_INTERVAL_HOURS`.
