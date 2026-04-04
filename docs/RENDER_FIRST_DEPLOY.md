# Render First Deployment (ProtoRyde Backend)

This guide is for first-time Render users deploying `Buropav/protoryde-backend`.

## 1) Before opening Render

From your terminal:

```bash
cd protoryde-backend
./scripts/render_preflight.sh
```

If preflight passes, deploy.

## 2) Create backend with Blueprint

1. Open Render dashboard.
2. Click `New +` -> `Blueprint`.
3. Connect GitHub if needed.
4. Select repo: `Buropav/protoryde-backend`.
5. Render detects `render.yaml` and shows:
   - Web service: `protoryde-backend`
   - Postgres DB: `protoryde-db`
6. Click `Apply`/`Create`.

## 3) Verify environment values

In Render service settings, confirm these env vars exist:
- `DATABASE_URL` (auto-linked from Render Postgres)
- `ENABLE_SCHEDULER=false`
- `PYTHON_VERSION=3.11.11`

Start command should be:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Health check path:

```text
/health
```

## 4) Wait for first deploy

Deploy is successful only when:
- Build log ends without error.
- Service status is `Live`.
- Health check is passing.

## 5) Run live smoke test

Copy backend URL from Render (example `https://protoryde-backend.onrender.com`) and run:

```bash
BACKEND_URL=https://<your-service>.onrender.com ./scripts/render_live_smoke.sh
```

Expected result:
- Health endpoint returns JSON.
- Model status returns JSON.
- Bootstrap + simulate endpoints return JSON.
- Claims and policy endpoints return JSON.
- Policy PDF downloads to `/tmp/protoryde_policy.pdf`.

## 6) Share with frontend teammate

Give this API base URL:

```text
https://<your-service>.onrender.com/api
```

Frontend teammate should set:

```text
EXPO_PUBLIC_API_URL=https://<your-service>.onrender.com/api
```
