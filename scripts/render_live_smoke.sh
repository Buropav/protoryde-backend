#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${BACKEND_URL:-}" ]]; then
  echo "Usage: BACKEND_URL=https://<service>.onrender.com $0"
  exit 1
fi

BASE="${BACKEND_URL%/}"
RIDER_ID="${RIDER_ID:-rdr_demo_hsr}"

echo "Health check..."
curl -fsS "$BASE/health" >/tmp/protoryde_health.json
cat /tmp/protoryde_health.json

printf "\nModel status...\n"
curl -fsS "$BASE/api/premium/model-status" >/tmp/protoryde_model_status.json
cat /tmp/protoryde_model_status.json

printf "\nBootstrapping demo rider...\n"
curl -fsS -X POST "$BASE/api/demo/bootstrap" \
  -H "Content-Type: application/json" \
  -d "{\"rider_id\":\"$RIDER_ID\",\"name\":\"Demo Rider\",\"phone\":\"9999999999\",\"zone\":\"HSR Layout\",\"upi_id\":\"demo@upi\",\"exclusions_acknowledged\":true}" \
  >/tmp/protoryde_bootstrap.json
cat /tmp/protoryde_bootstrap.json

printf "\nSimulating trigger...\n"
curl -fsS -X POST "$BASE/api/triggers/simulate" \
  -H "Content-Type: application/json" \
  -d '{"zone":"HSR Layout","trigger_type":"HEAVY_RAIN","is_simulated":true,"duration_hours":9}' \
  >/tmp/protoryde_simulate.json
cat /tmp/protoryde_simulate.json

printf "\nReading claims...\n"
curl -fsS "$BASE/api/claims/$RIDER_ID" >/tmp/protoryde_claims.json
cat /tmp/protoryde_claims.json

printf "\nReading current policy...\n"
curl -fsS "$BASE/api/policies/$RIDER_ID/current" >/tmp/protoryde_policy.json
cat /tmp/protoryde_policy.json

printf "\nDownloading policy PDF...\n"
curl -fsSL "$BASE/api/policies/$RIDER_ID/current/document" -o /tmp/protoryde_policy.pdf
ls -lh /tmp/protoryde_policy.pdf

echo "Live smoke test passed."
