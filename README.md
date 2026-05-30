# Drone Delivery Triage Console

A focused full-stack demo for one operator decision: when a drone delivery nest loses capacity or demand spikes, what should be protected, deferred, or moved to ground fallback?

The project is intentionally scoped to one Zipline-style nest, six aircraft, a rolling queue, a simulated clock, capacity-aware triage, operator overrides, auditability, and live reconciliation checks.

## Stack

- `backend/`: FastAPI, SQLite, deterministic simulator, event-sourced state fold, triage engine.
- `frontend/`: Vite, React, TypeScript, dense operational console.
- API style: JSON REST plus polling. WebSockets/SSE are a documented future upgrade, not needed for this demo.

## Run Locally

Install backend dependencies:

```bash
python -m pip install -r backend/requirements.txt
```

Start the API:

```bash
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Install and start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Verification

Backend tests:

```bash
python -m pytest backend/tests -q
```

Frontend build:

```bash
cd frontend
npm run build
```

## Demo Script

1. Start from the normal board: fleet status, live clock, queue rank, active missions, and reconciliation checks are visible.
2. Click `Storm front`: roughly half the idle fleet becomes grounded, the nest degrades, and capacity pressure increases.
3. Review the triage panel: P0 and medical orders are protected, retail is deferred or sent to ground fallback, and FIFO baseline risk is shown.
4. Click `Apply plan` or override a single order. Manual overrides require operator and reason, and P0 deferral requires an explicit reason.
5. Click any order row to open its event-sourced timeline. Check the audit panel for attributed interventions and invariant status.

## API

- `GET /api/state`: folded current state, metrics, active missions, invariants.
- `GET /api/triage`: current triage plan plus FIFO baseline.
- `POST /api/scenarios/storm-front`
- `POST /api/scenarios/aircraft-down`
- `POST /api/scenarios/demand-spike`
- `POST /api/triage/apply`
- `POST /api/orders/{order_id}/override`
- `GET /api/orders/{order_id}/timeline`
- `GET /api/audit`
- `POST /api/sim/tick`
- `POST /api/sim/reset`

## Architecture Notes

The backend stores every change in an append-only SQLite `events` table. Current state is derived by folding the event log. That keeps the correctness story legible: order timelines are reconstructable, interventions are attributed, and reconciliation checks can be computed from the same source as the UI.

Triage ranking is intentionally explainable:

1. priority tier: `P0 > P1 > P2`
2. SLA urgency
3. payload efficiency as a tiebreaker

The generated plan partitions pending orders into `protect_now`, `defer`, and `ground_fallback`. P0 orders are never auto-deferred; a manual P0 deferral must carry a clear reason in the event log.

## Scope Guardrails

In scope: one nest, local simulator, deterministic seed data, disruption scenarios, triage, interventions, audit, timelines, reconciliation.

Out of scope: real maps, real weather feeds, real aircraft telemetry, autonomy, auth, multi-tenant operations, billing, ML forecasting, and multi-nest rerouting.
