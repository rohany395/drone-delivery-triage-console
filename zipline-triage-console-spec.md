# Drone Delivery Triage Console — Build Spec

> A focused operator decision-support tool: **when a Zipline nest's delivery capacity gets tight, what gives?**
> Built as a portfolio piece to demonstrate full-stack application engineering for Zipline's Application Software team — emphasis on real-time visibility, intervention, and correctness.

---

## 1. The problem (one paragraph)

A single Zipline nest has finite delivery capacity (a fleet of aircraft, charging slots, weather windows). Demand is mixed: emergency blood, vaccines, prescriptions, and retail/food orders all share the same fleet. When capacity drops or demand spikes, something has to give — and the *wrong* thing giving (a delayed unit of blood) has very different consequences from a deferred burrito. This tool gives an operator **real-time visibility** into that strain, **proposes a triage plan** that protects clinical-critical deliveries, lets the operator **intervene**, and keeps **every decision traceable**.

This maps directly to the JD's hardest bullet: *"keep the network moving when demand shifts, weather changes, assets degrade, or capacity gets tight."*

---

## 2. Persona & job-to-be-done

**Persona:** Nest operator (network operations). Watches a live board, acts when the network is under strain, accountable for SLA and — above all — for never letting a life-critical delivery slip silently.

**Job-to-be-done:** "When my capacity drops, tell me what's at risk, recommend what to protect and what to defer, let me override with a reason, and keep a record I can stand behind."

---

## 3. Scope guardrails (read this first)

**In scope**
- One nest, ~6 aircraft, a ~20–30 order rolling queue.
- A simulated clock that advances missions, batteries, and charging.
- 3 disruption scenarios you can inject on demand.
- A prioritization engine + triage plan generation.
- Operator intervention actions + an audit log.
- Event-sourced state so every order has a reconstructable timeline.

**Explicitly out of scope** (state this in your write-up — it signals judgment)
- Real maps / geographic routing / real weather feeds.
- Real aircraft telemetry or autonomy.
- Auth, multi-tenant, mobile, billing.
- ML demand forecasting (the simulator stands in for demand).
- More than one nest (reroute-to-neighbor is a stretch goal only).

The discipline *is* the point: this is one operator decision done well, not a god-dashboard clone of their NOC.

---

## 4. Domain model

Model **every state change as an appended event**, and derive current state by folding the event log. This is the spine of the correctness story and mirrors their Kafka/event-driven world.

### Core entities

| Entity | Key fields | States |
|---|---|---|
| `Nest` | id, name, weather_state, charging_slots | `nominal` / `degraded` |
| `Aircraft` | id, model (P1/P2), battery_pct, hours_since_service, current_mission_id | `ready` / `in_flight` / `charging` / `maintenance` / `grounded` |
| `Order` | id, vertical, priority_tier (derived), payload_kg, created_at, promised_by, destination, urgency_flag | `pending` / `assigned` / `in_flight` / `delivered` / `deferred` / `ground_fallback` / `failed` |
| `Mission` | id, order_id, aircraft_id, launched_at, eta | `active` / `complete` / `aborted` |
| `Event` | id, ts, type, entity_ref, payload, actor (`system`/`operator`) | append-only |
| `Intervention` | id, ts, type, order_ref, operator, reason | append-only |

### Verticals → priority tiers

| Tier | Verticals | Rule |
|---|---|---|
| **P0 — critical clinical** | emergency blood, time-critical biologics | Never auto-deferred. Override requires explicit logged reason. |
| **P1 — routine medical** | vaccines, prescriptions, lab samples | SLA-bound; deferred only after retail is exhausted. |
| **P2 — retail / food** | Walmart goods, restaurant orders | First to defer or push to ground fallback. |

---

## 5. Core mechanics

### Capacity model (keep it legible)
- Each delivery = `T_flight` (round trip) then `T_charge` before the aircraft is `ready` again.
- Sustainable throughput ≈ `operational_aircraft / (T_flight + T_charge)` deliveries per unit time.
- **Capacity tight** = incoming demand rate > throughput → backlog grows, SLA timers approach breach.
- Weather/maintenance reduce `operational_aircraft` (and can inflate `T_flight`).

### Prioritization engine (the heart — make it explainable)
Score each pending order, sort, assign to `ready` aircraft top-down:
1. **Priority tier** (P0 > P1 > P2) — dominant term.
2. **SLA urgency** — time remaining to `promised_by`.
3. **Efficiency** — payload / range tiebreak.

Crucially: every ranking must be **explainable in one human line** ("P0 emergency blood — protected" / "P2 retail — deferred 18 min, no SLA breach"). Transparency is the operational-trust signal.

### Triage plan
When capacity < demand, generate a plan that partitions the queue into **Protect now / Defer / Ground fallback**, and report consequences:
- units of blood / medical orders protected,
- retail orders deferred and by roughly how long,
- SLA breaches avoided vs. a naive FIFO baseline.

Always show the FIFO baseline alongside — it makes the value obvious.

### Disruption scenarios (the simulator)
1. **Storm front** — grounds ~half the fleet for a window.
2. **Aircraft down** — one unit → `maintenance` (asset degradation).
3. **Demand spike** — a burst of new orders (e.g., a hospital emergency batch + a lunch rush) arrives at once.

---

## 6. Correctness invariants (do not skip — this is what sells the role)

Surface these as live, checkable guarantees:
- **No lost orders:** every order is in exactly one state; the running tally always reconciles.
- **No double-assignment:** an aircraft has ≤1 active mission; an order has ≤1 aircraft.
- **Full traceability:** an order's complete history is reconstructable purely from its events.
- **Reversible, attributed interventions:** each carries an operator + reason; sensible ones can be undone.
- **P0 protection:** clinical-critical orders cannot be auto-deferred — only explicitly overridden, with a logged reason.

A small **reconciliation panel** that proves these hold in real time is worth more than another feature.

---

## 7. Screens

1. **Ops board (main)**
   - Top: nest status, weather, and a **capacity gauge** (demand vs. throughput) that flips amber→red under strain.
   - Left: fleet panel — aircraft cards with state + battery + ETA.
   - Center: order queue — color-coded by tier, live SLA countdowns, current rank.

2. **Triage panel** (appears when capacity is tight)
   - The proposed plan: Protect / Defer / Ground fallback, with a one-line rationale per affected order and the consequence summary vs. FIFO baseline.
   - Actions: **Apply plan**, or override any single order (forces a reason prompt).

3. **Order timeline** (click any order)
   - Event-sourced history: created → prioritized → assigned → in-flight → delivered, or deferred/overridden with reason and operator.

4. **Audit & reconciliation panel** *(small but high-value)*
   - Running invariant checks (orders accounted, no double-assignments) + the full intervention log.

---

## 8. The "wow" interaction (build toward this)

Click **Inject: Storm front** →
1. Half the fleet flips to `grounded`; the capacity gauge goes red; backlog spikes.
2. The triage panel auto-surfaces a plan that **protects every unit of blood and defers retail**, each with a human-readable justification.
3. Operator clicks **Apply plan** (or overrides one order, supplying a reason).
4. The queue reorders live, SLA timers recompute, and the audit log records *who did what and why*.

That's real-time visibility + intervention + correctness + mission alignment in ~10 seconds.

---

## 9. Tech approach (mirror their stack, stay pragmatic)

| Layer | Prototype choice | Why / scale note |
|---|---|---|
| Frontend | **React** | Their stack. |
| State | **Event-sourced**: append events, fold to derive state | Mirrors Kafka/gRPC thinking; gives traceability for free. |
| Backend | **Go or Python** service, small **REST or gRPC** API | Optional for a front-end-only demo, but a thin service shows full-stack range. |
| Storage | **Postgres** (orders, aircraft, `events` table) | Their stack; the `events` table *is* the log. |
| Clock | A tick loop advancing missions/batteries/charging | Drives the "live" feel with no hardware. |
| Observability | A tiny metrics strip (throughput, backlog, SLA breaches) | A nod to Grafana/Honeycomb. |

You can ship a convincing version as a single React app with an in-memory event log and a simulated clock. Add the Go/Python + Postgres layer if you want to flex backend depth — note in the README where you'd split into services at scale.

---

## 10. Build order (milestones for your agents)

- **M1 — Engine:** domain model + event log + simulated clock; orders flow through states automatically (no disruptions yet). Assert the invariants in tests.
- **M2 — Board:** React ops board — live fleet, queue, capacity gauge.
- **M3 — Triage:** disruption injector + prioritization engine + triage plan vs. FIFO baseline.
- **M4 — Intervention:** operator actions + reason prompts + audit log + order timeline.
- **M5 — Polish (stretch):** reconciliation panel, metrics strip, reroute-to-second-nest.

Stop after M4 and you have a complete, demoable, defensible piece.

---

## 11. 90-second demo script

1. "This is a single nest under normal load — fleet healthy, queue flowing, every order traceable." *(show board + click one order's timeline)*
2. "Now a storm front grounds half the fleet." *(inject; gauge goes red)*
3. "The system immediately flags what's at risk and proposes a plan that protects all clinical-critical deliveries and defers retail — here's the reasoning, and here's how it beats naive FIFO." *(show triage panel)*
4. "The operator stays in control — I'll override this one and it forces a reason, which gets logged." *(override; show audit entry)*
5. "And throughout, nothing is lost or double-assigned — here's the live reconciliation." *(show audit panel)*

---

## 12. How to frame it in your application

- Lead with the problem in *their* words: keeping the network moving when capacity gets tight.
- Call it a **focused demonstration** of how you'd approach their real-time-visibility-and-intervention problem — explicitly **not** a claim they lack a NOC. This pre-empts the obvious objection and reads as product maturity.
- Emphasize the trifecta the JD repeats: **product instinct** (you picked one hard operator decision), **systems judgment** (event-sourced correctness), and **operational trust** (auditability, P0 protection, reconciliation).
- Mention the scope guardrails out loud — knowing what *not* to build is a senior signal.
