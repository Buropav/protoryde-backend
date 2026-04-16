# ProtoRyde Backend API Contract

This document is the integration contract for the frontend.

## Base
- Prefix: `/api`
- Content type: JSON unless noted
- Time format: ISO 8601
- Currency: `INR`

## Core Flows

### 1) Demo Bootstrap
- `POST /demo/bootstrap`
- Purpose: create/update demo rider + active policy in one call
- Request:
```json
{
  "rider_id": "rdr_demo_hsr",
  "rider_name": "Pranav",
  "zone": "HSR Layout",
  "upi_id": "pranav@okicici",
  "exclusions_accepted": true
}
```

### 2) Premium Prediction
- `POST /premium/predict`
- Purpose: ML-first premium prediction with fallback to rule engine
- Request keys:
  - `zone` (required)
  - `prefer_ml` (default `true`)
  - optional: `zone_risk_score`, `weather_severity`, `claim_history`
  - optional: `forecast_features`, `rider_features`
- Response keys:
  - `engine` (`ml_shap` or `rule_engine`)
  - `base_premium`, `final_premium`, `adjustments[]`
  - `model_status`

### 3) Trigger Simulation
- `POST /triggers/simulate`
- Purpose: create deterministic claim simulation
- Critical response keys:
  - `simulation_id`
  - `trigger_event`
  - `claims_preview[0].fraud_layers[]`
  - `claims_preview[0].recommended_payout`

## Policy + Claims

### 4) Policy Activation
- `POST /policies/activate`
- Requires `exclusions_accepted=true`

### 5) Current Policy
- `GET /policies/{rider_id}/current`

### 6) Policy History
- `GET /policies/{rider_id}/history`

### 7) Policy PDF
- `GET /policies/{rider_id}/current/document`
- Response type: `application/pdf`

### 8) Rider Claims
- `GET /claims/{rider_id}`

### 9) Admin Management (Phase 3)
- `GET /admin/metrics`: returns `{active_policies, total_premiums, total_claims_paid}`
- `GET /admin/claims_map`: returns `{claims: [{id, latitude, longitude, payout_amount, ...}]}`
- `GET /admin/fraud_flags`: returns `{flags: [{claim_id, rider_id, fraud_layers, ...}]}`
- `GET /admin/predictions`: same as `/forecast/HSR Layout`

### 10) Policy Upgrades (Phase 3)
- `POST /policy/{id}/upgrade`: Boosts premium by ₹25, caps payout at ₹2800

### 11) Rider Calendar (Phase 3)
- `GET /rider/{id}/calendar`: 7-day unified earnings timeline

## Supporting Endpoints
- `GET /exclusions`
- `GET /premium/model-status`
- `GET /policy/eligibility?zone=...`
- `GET /enrollment/eligibility?zone=...`
- `GET /weather/current/{zone}?is_simulated=true|false`
- `GET /weather/warnings/{zone}?is_simulated=true|false`
- `GET /mock/delhivery/{zone}/{date}`
- `GET /mock/branches/{zone}`

## Fraud Layer Contract (fixed order)
1. `L1_WEATHER_THRESHOLD`
2. `L2_ZONE_PRESENCE`
3. `L3_DELHIVERY_CROSS_REF`
4. `L4_BRANCH_CLOSURE_CHECK`

Each layer returns:
- `layer`
- `passed`
- `reason`
- `evidence`
