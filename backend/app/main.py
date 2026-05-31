from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

from .engine import (
    EventStore,
    apply_triage,
    audit,
    fold,
    inject_aircraft_down,
    inject_demand_spike,
    inject_storm,
    make_triage,
    override_order,
    seed,
    tick,
    timeline,
)

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "*")
DB_PATH = Path(os.environ.get("TRIAGE_DB_PATH",
    str(Path(__file__).resolve().parent.parent / "data" / "triage_events.sqlite")))
store = EventStore(DB_PATH)
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "triage_events.sqlite"
store = EventStore(DB_PATH)

app = FastAPI(title="Drone Delivery Triage Console API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN] if FRONTEND_ORIGIN != "*" else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TickRequest(BaseModel):
    minutes: int = 1


class ApplyRequest(BaseModel):
    operator: str = "ops-console"


class OverrideRequest(BaseModel):
    target_action: str
    operator: str
    reason: str


@app.on_event("startup")
def ensure_seeded() -> None:
    if not store.list():
        seed(store)


@app.get("/api/state")
def get_state():
    return fold(store.list())


@app.get("/api/triage")
def get_triage():
    return make_triage(fold(store.list()))


@app.post("/api/scenarios/storm-front")
def storm_front():
    return inject_storm(store)


@app.post("/api/scenarios/aircraft-down")
def aircraft_down():
    return inject_aircraft_down(store)


@app.post("/api/scenarios/demand-spike")
def demand_spike():
    return inject_demand_spike(store)


@app.post("/api/triage/apply")
def post_apply_triage(body: ApplyRequest):
    return apply_triage(store, body.operator)


@app.post("/api/orders/{order_id}/override")
def post_override(order_id: str, body: OverrideRequest):
    try:
        return override_order(store, order_id, body.target_action, body.operator, body.reason)
    except (StopIteration, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/orders/{order_id}/timeline")
def get_timeline(order_id: str):
    return {"order_id": order_id, "events": timeline(store, order_id)}


@app.get("/api/audit")
def get_audit():
    return {"entries": audit(store)}


@app.post("/api/sim/tick")
def post_tick(body: TickRequest = TickRequest()):
    return tick(store, max(1, min(body.minutes, 10)))


@app.post("/api/sim/reset")
def post_reset():
    return seed(store)
