# Drone Delivery Triage Console

**Live demo:** https://drone-delivery-triage-console-jv5pmjc1g.vercel.app/
*(Backend runs on a free Render instance that sleeps when idle — the first load after inactivity may take 30–60s to wake. Give it a moment.)*

A focused full-stack tool for one hard operator decision: **when a drone-delivery nest loses capacity or demand spikes, what gets protected, what gets deferred, and what falls back to ground transport?**

When a storm grounds aircraft or a hospital emergency batch lands all at once, a unit of emergency blood and a retail order are competing for the same fleet — and the wrong thing slipping has very different consequences. This console gives a nest operator real-time visibility into that strain, proposes a triage plan that protects clinical-critical deliveries, lets the operator intervene with an attributed reason, and proves on screen that nothing is lost or double-assigned along the way.

It is built as a focused demonstration of how I'd approach the kind of operational software in  brief — *"keep the network moving when demand shifts, weather changes, assets degrade, or capacity gets tight"*.

---

## What it does

- **Live ops board** — a single nest, six aircraft, and a rolling order queue advancing on a simulated clock you control (Step / Play / Pause). A capacity gauge flips from healthy to constrained as strain builds.
- **Explainable triage** — when capacity can't meet demand, the engine ranks orders by priority tier → SLA urgency → payload efficiency and partitions them into *protect now / defer / ground fallback*, each with a one-line human-readable rationale, shown against a naive FIFO baseline so the value is obvious.
- **Operator intervention** — apply the plan wholesale or override any single order; overrides require an operator and a reason, and deferring a clinical-critical (P0) order demands an explicit logged justification.
- **Auditability and live reconciliation** — every state change is an appended event; an order's full timeline is reconstructable from the log, and a reconciliation panel continuously proves five correctness invariants hold.

## Try it (90-second walkthrough)

1. The board loads **paused** and healthy — fleet ready, queue flowing, reconciliation all green. Click any order to see its event-sourced timeline.
2. Click **Step** a few times to advance the clock and watch orders get assigned, fly, deliver, and recharge.
3. Click **Storm front** — aircraft are grounded, the gauge goes red, and the triage panel activates with a plan that protects every medical order and defers retail.
4. Click **Apply plan**, or **Override** one order with a reason — the action is logged with your name and shows in the audit panel.
5. Throughout, the reconciliation panel confirms no order is lost or double-assigned, and no P0 was deferred without authorization.

---

## Architecture

The backend is **event-sourced**: every change — order created, mission launched, mission aborted, operator override — is an immutable row in an append-only `events` table. Current state is derived by *folding* that log on each read. This is the spine of the correctness story:

- **Order timelines are reconstructable** purely from events.
- **Interventions are attributed** (operator + reason) and live in the same log.
- **Reconciliation checks read from the same source as the UI**, so what the operator sees and what the system guarantees can't drift apart.

The five invariants are deliberately *substantive*, not just state-validity checks:

| Invariant | What it actually verifies |
|---|---|
| No lost orders | Conservation: every created order appears exactly once in the folded state — none dropped, none duplicated |
| No double-assignment | No aircraft or order is bound to more than one active mission |
| Timeline reconstructable | Replaying an order's own events reproduces its current folded state |
| Attributed interventions | Every operator action carries a non-empty operator and reason |
| P0 protection | A deferred clinical-critical order exists only if a logged override authorized it — silent/automatic P0 deferral is forbidden |

## Tech stack

- **Backend:** FastAPI, SQLite (append-only event store), a deterministic simulator, an event-fold state derivation, and an explainable triage engine. Pytest suite covers the invariants and scenarios.
- **Frontend:** Vite + React + TypeScript — a dense operational console.
- **API style:** JSON REST with polling. WebSocket/SSE push is a documented future upgrade, not needed for this demo.

## Run locally

Backend:

```bash
python -m pip install -r backend/requirements.txt
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

Backend tests:

```bash
python -m pytest backend/tests -q
```

## Deployment

- **Frontend** is deployed to Vercel (static Vite build). The API base is configured via the `VITE_API_URL` environment variable.
- **Backend** is deployed to Render as a persistent service, with CORS locked to the frontend origin via `FRONTEND_ORIGIN`.

---

*Built by Rohan as a portfolio project. Feedback welcome.*