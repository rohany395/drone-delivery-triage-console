from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4


BASE_TS = 1_779_996_600
FLIGHT_MINUTES = 18
CHARGE_MINUTES = 10

TIER_RANK = {"P0": 0, "P1": 1, "P2": 2}
VERTICAL_TIER = {
    "emergency blood": "P0",
    "time-critical biologics": "P0",
    "vaccines": "P1",
    "prescriptions": "P1",
    "lab samples": "P1",
    "retail": "P2",
    "food": "P2",
}


@dataclass
class Event:
    id: int
    ts: int
    type: str
    entity_type: str
    entity_id: str
    actor: str
    payload: dict[str, Any]


class EventStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )

    def reset(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM events")

    def append(
        self,
        type: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
        actor: str = "system",
        ts: int | None = None,
    ) -> Event:
        with self._connect() as conn:
            if ts is None:
                row = conn.execute("SELECT COALESCE(MAX(ts), ?) + 1 AS ts FROM events", (BASE_TS,)).fetchone()
                ts = int(row["ts"])
            cur = conn.execute(
                "INSERT INTO events (ts, type, entity_type, entity_id, actor, payload) VALUES (?, ?, ?, ?, ?, ?)",
                (ts, type, entity_type, entity_id, actor, json.dumps(payload, sort_keys=True)),
            )
            return Event(int(cur.lastrowid), ts, type, entity_type, entity_id, actor, payload)

    def list(self) -> list[Event]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM events ORDER BY id ASC").fetchall()
        return [
            Event(
                id=int(row["id"]),
                ts=int(row["ts"]),
                type=str(row["type"]),
                entity_type=str(row["entity_type"]),
                entity_id=str(row["entity_id"]),
                actor=str(row["actor"]),
                payload=json.loads(str(row["payload"])),
            )
            for row in rows
        ]


def tier_for(vertical: str) -> str:
    return VERTICAL_TIER.get(vertical, "P2")


def event_to_dict(event: Event, clock: int | None = None) -> dict[str, Any]:
    return {
        "id": event.id,
        "ts": event.ts,
        "clock": clock,
        "type": event.type,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "actor": event.actor,
        "payload": event.payload,
    }


def seed(store: EventStore) -> dict[str, Any]:
    store.reset()
    store.append(
        "NEST_CREATED",
        "nest",
        "NEST-01",
        {"name": "South Bay Nest", "weather_state": "nominal", "charging_slots": 3, "status": "nominal"},
        ts=BASE_TS,
    )
    store.append("CLOCK_SET", "sim", "clock", {"minute": 0}, ts=BASE_TS + 1)
    for idx in range(1, 7):
        state = "ready" if idx <= 4 else "charging"
        store.append(
            "AIRCRAFT_CREATED",
            "aircraft",
            f"Z-{idx:02d}",
            {
                "model": "P2" if idx % 2 == 0 else "P1",
                "battery_pct": 92 - idx * 4,
                "hours_since_service": 18 + idx * 7,
                "state": state,
                "charge_complete_at": 4 if state == "charging" else None,
            },
            ts=BASE_TS + 1 + idx,
        )

    verticals = [
        "emergency blood",
        "vaccines",
        "retail",
        "prescriptions",
        "food",
        "lab samples",
        "retail",
        "time-critical biologics",
        "food",
        "retail",
        "vaccines",
        "prescriptions",
        "retail",
        "food",
        "lab samples",
        "retail",
        "emergency blood",
        "prescriptions",
        "food",
        "retail",
        "vaccines",
        "retail",
        "lab samples",
        "food",
    ]
    destinations = ["Mercy Hospital", "County Clinic", "North Lab", "Walmart Hub", "Riverside Cafe", "Hill Pharmacy"]
    for idx, vertical in enumerate(verticals, start=1):
        tier = tier_for(vertical)
        promised = 22 + idx * 3 if tier == "P0" else 36 + idx * 4 if tier == "P1" else 48 + idx * 5
        store.append(
            "ORDER_CREATED",
            "order",
            f"O-{idx:03d}",
            {
                "vertical": vertical,
                "priority_tier": tier,
                "payload_kg": round(0.8 + (idx % 5) * 0.35, 2),
                "created_at": max(0, idx - 8),
                "promised_by": promised,
                "destination": destinations[idx % len(destinations)],
                "urgency_flag": tier == "P0" or promised < 55,
                "state": "pending",
            },
            ts=BASE_TS + 20 + idx,
        )
    return fold(store.list())


def fold(events: list[Event]) -> dict[str, Any]:
    state: dict[str, Any] = {
        "clock": 0,
        "nest": {},
        "fleet": {},
        "orders": {},
        "missions": {},
        "interventions": [],
        "events": [],
    }
    for event in events:
        p = event.payload
        if event.type == "CLOCK_SET":
            state["clock"] = int(p["minute"])
        elif event.type == "CLOCK_ADVANCED":
            state["clock"] += int(p.get("minutes", 1))
        elif event.type == "NEST_CREATED":
            state["nest"] = {"id": event.entity_id, **p}
        elif event.type == "NEST_WEATHER_SET":
            state["nest"].update(p)
        elif event.type == "AIRCRAFT_CREATED":
            state["fleet"][event.entity_id] = {"id": event.entity_id, "current_mission_id": None, **p}
        elif event.type == "AIRCRAFT_STATUS_SET":
            state["fleet"].setdefault(event.entity_id, {"id": event.entity_id}).update(p)
        elif event.type == "AIRCRAFT_BATTERY_SET":
            state["fleet"].setdefault(event.entity_id, {"id": event.entity_id}).update({"battery_pct": p["battery_pct"]})
        elif event.type == "ORDER_CREATED":
            state["orders"][event.entity_id] = {"id": event.entity_id, "assigned_aircraft_id": None, "mission_id": None, **p}
        elif event.type in {"ORDER_STATE_SET", "ORDER_ASSIGNED"}:
            state["orders"].setdefault(event.entity_id, {"id": event.entity_id}).update(p)
        elif event.type == "MISSION_LAUNCHED":
            mission = {
                "id": event.entity_id,
                "state": "active",
                "order_id": p["order_id"],
                "aircraft_id": p["aircraft_id"],
                "launched_at": p["launched_at"],
                "eta": p["eta"],
            }
            state["missions"][event.entity_id] = mission
            state["orders"][p["order_id"]].update(
                {"state": "in_flight", "mission_id": event.entity_id, "assigned_aircraft_id": p["aircraft_id"]}
            )
            state["fleet"][p["aircraft_id"]].update({"state": "in_flight", "current_mission_id": event.entity_id})
        elif event.type == "MISSION_COMPLETED":
            mission = state["missions"].setdefault(event.entity_id, {"id": event.entity_id})
            mission.update({"state": "complete", "completed_at": p["completed_at"]})
            order_id = mission.get("order_id", p.get("order_id"))
            aircraft_id = mission.get("aircraft_id", p.get("aircraft_id"))
            if order_id and order_id in state["orders"]:
                state["orders"][order_id].update({"state": "delivered"})
            if aircraft_id and aircraft_id in state["fleet"]:
                state["fleet"][aircraft_id].update(
                    {
                        "state": "charging",
                        "battery_pct": max(15, int(state["fleet"][aircraft_id].get("battery_pct", 80)) - 24),
                        "current_mission_id": None,
                        "charge_complete_at": p["completed_at"] + CHARGE_MINUTES,
                    }
                )
        elif event.type == "MISSION_ABORTED":
            mission = state["missions"].setdefault(
                event.entity_id,
                {"id": event.entity_id, "order_id": p.get("order_id"), "aircraft_id": p.get("aircraft_id")},
            )
            mission.update({"state": "aborted", "aborted_at": p["aborted_at"], "reason": p.get("reason", "aborted")})
            order_id = mission.get("order_id", p.get("order_id"))
            aircraft_id = mission.get("aircraft_id", p.get("aircraft_id"))
            if order_id and order_id in state["orders"]:
                state["orders"][order_id].update({"state": "pending", "assigned_aircraft_id": None, "mission_id": None})
            if aircraft_id and aircraft_id in state["fleet"]:
                state["fleet"][aircraft_id].update(
                    {
                        "state": "grounded",
                        "current_mission_id": None,
                        "charge_complete_at": None,
                        "grounded_until": p.get("grounded_until"),
                    }
                )
        elif event.type == "INTERVENTION_RECORDED":
            state["interventions"].append({"id": event.id, "ts": event.ts, **p})
        state["events"].append(event)

    orders = list(state["orders"].values())
    active_missions = [m for m in state["missions"].values() if m.get("state") == "active"]
    pending = [o for o in orders if o.get("state") == "pending"]
    risky = [o for o in orders if o.get("state") in {"pending", "assigned", "in_flight"} and o["promised_by"] - state["clock"] <= 18]
    operational = [a for a in state["fleet"].values() if a.get("state") in {"ready", "charging", "in_flight"}]
    ready = [a for a in state["fleet"].values() if a.get("state") == "ready"]
    throughput = round(len(operational) / ((FLIGHT_MINUTES + CHARGE_MINUTES) / 60), 1)
    demand_rate = round(max(1, len(pending)) / 2.2, 1)

    state["fleet"] = sorted(state["fleet"].values(), key=lambda a: a["id"])
    state["orders"] = sorted(orders, key=lambda o: order_sort_key(o, state["clock"]))
    state["active_missions"] = sorted(active_missions, key=lambda m: m["eta"])
    state["metrics"] = {
        "backlog": len(pending),
        "ready_aircraft": len(ready),
        "operational_aircraft": len(operational),
        "throughput_per_hour": throughput,
        "demand_per_hour": demand_rate,
        "sla_risk": len(risky),
        "capacity_tight": len(pending) > max(8, len(operational) * 5) or demand_rate > throughput * 1.15,
    }
    state["invariants"] = check_invariants(state, events)
    del state["events"]
    return state


def order_sort_key(order: dict[str, Any], clock: int) -> tuple[int, int, float]:
    return (
        TIER_RANK.get(order.get("priority_tier", "P2"), 2),
        int(order.get("promised_by", 999)) - clock,
        -float(order.get("payload_kg", 1)),
    )


def rationale(order: dict[str, Any], action: str, clock: int) -> str:
    tier = order["priority_tier"]
    remaining = order["promised_by"] - clock
    if action == "protect_now":
        return f"{tier} {order['vertical']} protected; SLA due in {remaining} min."
    if action == "defer":
        return f"{tier} {order['vertical']} deferred; lower priority and {remaining} min SLA buffer."
    return f"{tier} {order['vertical']} moved to ground fallback to preserve aircraft capacity."


def make_triage(state: dict[str, Any]) -> dict[str, Any]:
    pending = [o for o in state["orders"] if o["state"] == "pending"]
    ranked = sorted(pending, key=lambda o: order_sort_key(o, state["clock"]))
    ready = state["metrics"]["ready_aircraft"]
    operational = state["metrics"]["operational_aircraft"]
    protect_slots = max(ready, min(len(ranked), max(2, operational)))
    protect_ids = {o["id"] for o in ranked[:protect_slots]}
    p0_ids = {o["id"] for o in ranked if o["priority_tier"] == "P0"}
    protect_ids |= p0_ids

    plan = {"protect_now": [], "defer": [], "ground_fallback": []}
    for order in ranked:
        if order["id"] in protect_ids:
            action = "protect_now"
        elif order["priority_tier"] == "P2" and (order["promised_by"] - state["clock"]) > 35:
            action = "defer"
        else:
            action = "ground_fallback"
        plan[action].append({"order_id": order["id"], "rationale": rationale(order, action, state["clock"]), "committed": False})

    recommendation_plan = {key: list(items) for key, items in plan.items()}
    committed_columns = {"deferred": "defer", "ground_fallback": "ground_fallback"}
    committed_items = {"defer": [], "ground_fallback": []}
    for order in state["orders"]:
        column = committed_columns.get(order["state"])
        if not column:
            continue
        for items in plan.values():
            items[:] = [item for item in items if item["order_id"] != order["id"]]
        committed_items[column].append(
            {
                "order_id": order["id"],
                "rationale": committed_rationale(state, order["id"]),
                "committed": True,
            }
        )
    plan["defer"] = committed_items["defer"] + plan["defer"]
    plan["ground_fallback"] = committed_items["ground_fallback"] + plan["ground_fallback"]

    fifo = sorted(pending, key=lambda o: (o["created_at"], o["id"]))
    fifo_protected = fifo[:protect_slots]
    fifo_deferred = fifo[protect_slots:]
    triage_deferred_p0 = 0
    fifo_deferred_p0 = len([o for o in fifo_deferred if o["priority_tier"] == "P0"])
    medical_protected = len(
        [item for item in recommendation_plan["protect_now"] if state_order(state, item["order_id"])["priority_tier"] in {"P0", "P1"}]
    )
    return {
        "capacity_tight": state["metrics"]["capacity_tight"],
        "generated_at_clock": state["clock"],
        "plan": plan,
        "summary": {
            "medical_orders_protected": medical_protected,
            "retail_deferred": len(
                [item for item in recommendation_plan["defer"] if state_order(state, item["order_id"])["priority_tier"] == "P2"]
            ),
            "p0_auto_deferred": triage_deferred_p0,
            "sla_breaches_avoided_vs_fifo": fifo_deferred_p0,
            "estimated_delay_minutes": 24 if state["metrics"]["capacity_tight"] else 8,
        },
        "fifo_baseline": {
            "protect_now": [o["id"] for o in fifo_protected],
            "deferred_p0_count": fifo_deferred_p0,
            "risk": "FIFO can spend scarce launches on low-priority early retail before newer clinical-critical orders.",
        },
    }


def committed_rationale(state: dict[str, Any], order_id: str) -> str:
    interventions = [item for item in state.get("interventions", []) if item.get("order_id") == order_id]
    if not interventions:
        return "Already moved; committed state."
    latest = sorted(interventions, key=lambda item: item["id"])[-1]
    if latest.get("type") == "manual_override":
        return "Moved by operator override."
    if latest.get("type") == "triage_apply":
        return "Moved by applied triage plan."
    return "Already moved; committed state."


def state_order(state: dict[str, Any], order_id: str) -> dict[str, Any]:
    return next(o for o in state["orders"] if o["id"] == order_id)


def reconstruct_order_state(events: list[Event], order_id: str) -> dict[str, Any] | None:
    order: dict[str, Any] | None = None
    related_missions: set[str] = set()
    for event in events:
        p = event.payload
        if event.type == "ORDER_CREATED" and event.entity_id == order_id:
            order = {"id": event.entity_id, "assigned_aircraft_id": None, "mission_id": None, **p}
        elif event.type in {"ORDER_STATE_SET", "ORDER_ASSIGNED"} and event.entity_id == order_id:
            if order is None:
                order = {"id": event.entity_id}
            order.update(p)
        elif event.type == "MISSION_LAUNCHED" and p.get("order_id") == order_id:
            related_missions.add(event.entity_id)
            if order is None:
                order = {"id": order_id}
            order.update({"state": "in_flight", "mission_id": event.entity_id, "assigned_aircraft_id": p["aircraft_id"]})
        elif event.type == "MISSION_COMPLETED" and (p.get("order_id") == order_id or event.entity_id in related_missions):
            if order is None:
                order = {"id": order_id}
            order.update({"state": "delivered"})
        elif event.type == "MISSION_ABORTED" and (p.get("order_id") == order_id or event.entity_id in related_missions):
            if order is None:
                order = {"id": order_id}
            order.update({"state": "pending", "assigned_aircraft_id": None, "mission_id": None})
    return order


def check_invariants(state: dict[str, Any], events: list[Event]) -> list[dict[str, Any]]:
    orders = state["orders"] if isinstance(state["orders"], list) else list(state["orders"].values())
    active = state["active_missions"] if "active_missions" in state else [m for m in state["missions"].values() if m.get("state") == "active"]
    aircraft_counts: dict[str, int] = {}
    order_counts: dict[str, int] = {}
    for mission in active:
        aircraft_counts[mission["aircraft_id"]] = aircraft_counts.get(mission["aircraft_id"], 0) + 1
        order_counts[mission["order_id"]] = order_counts.get(mission["order_id"], 0) + 1

    created_ids = [event.entity_id for event in events if event.type == "ORDER_CREATED"]
    created_set = set(created_ids)
    live_ids = [order["id"] for order in orders]
    live_set = set(live_ids)
    duplicate_created = sorted({order_id for order_id in created_ids if created_ids.count(order_id) > 1})
    duplicate_live = sorted({order_id for order_id in live_ids if live_ids.count(order_id) > 1})
    missing = sorted(created_set - live_set)
    extra = sorted(live_set - created_set)
    no_lost_ok = not duplicate_created and not duplicate_live and created_set == live_set

    drifted = []
    for order in orders:
        reconstructed = reconstruct_order_state(events, order["id"])
        if reconstructed != order:
            drifted.append(order["id"])

    authorized_p0_deferrals = {
        intervention["order_id"]
        for intervention in state.get("interventions", [])
        if intervention.get("type") == "manual_override"
        and intervention.get("target_action") == "deferred"
        and bool(str(intervention.get("operator", "")).strip())
        and bool(str(intervention.get("reason", "")).strip())
    }
    unauthorized_p0_deferrals = sorted(
        order["id"]
        for order in orders
        if order.get("priority_tier") == "P0" and order.get("state") == "deferred" and order["id"] not in authorized_p0_deferrals
    )

    return [
        {
            "name": "No lost orders",
            "ok": no_lost_ok,
            "detail": (
                f"{len(created_set)} created, {len(live_set)} folded. "
                f"duplicate_created={duplicate_created or 'none'}, duplicate_live={duplicate_live or 'none'}, "
                f"missing={missing or 'none'}, extra={extra or 'none'}."
            ),
        },
        {
            "name": "No double-assignment",
            "ok": all(count <= 1 for count in aircraft_counts.values()) and all(count <= 1 for count in order_counts.values()),
            "detail": f"{len(active)} active missions checked.",
        },
        {
            "name": "Timeline reconstructable",
            "ok": not drifted,
            "detail": f"Drifted order ids: {drifted or 'none'}.",
        },
        {
            "name": "Attributed interventions",
            "ok": all(i.get("operator") and i.get("reason") for i in state.get("interventions", [])),
            "detail": f"{len(state.get('interventions', []))} interventions include actor and reason.",
        },
        {
            "name": "P0 protection",
            "ok": not unauthorized_p0_deferrals,
            "detail": f"Unauthorized P0 deferrals: {unauthorized_p0_deferrals or 'none'}.",
        },
    ]


def tick(store: EventStore, minutes: int = 1) -> dict[str, Any]:
    before = fold(store.list())
    new_clock = before["clock"] + minutes
    store.append("CLOCK_ADVANCED", "sim", "clock", {"minutes": minutes})
    for mission in before["active_missions"]:
        if mission["eta"] <= new_clock:
            store.append(
                "MISSION_COMPLETED",
                "mission",
                mission["id"],
                {"completed_at": new_clock, "order_id": mission["order_id"], "aircraft_id": mission["aircraft_id"]},
            )
    state = fold(store.list())
    for aircraft in state["fleet"]:
        if aircraft["state"] == "charging" and aircraft.get("charge_complete_at") is not None and aircraft["charge_complete_at"] <= new_clock:
            store.append("AIRCRAFT_STATUS_SET", "aircraft", aircraft["id"], {"state": "ready", "battery_pct": 96, "charge_complete_at": None})
    state = fold(store.list())
    if state["nest"].get("weather_state") == "storm_front":
        return state
    ready_aircraft = [a for a in state["fleet"] if a["state"] == "ready" and a["battery_pct"] >= 35]
    pending = [o for o in state["orders"] if o["state"] == "pending"]
    for aircraft, order in zip(ready_aircraft, sorted(pending, key=lambda o: order_sort_key(o, state["clock"]))):
        mission_id = f"M-{uuid4().hex[:8].upper()}"
        eta = state["clock"] + (FLIGHT_MINUTES + (6 if state["nest"].get("weather_state") == "storm_front" else 0))
        store.append("ORDER_ASSIGNED", "order", order["id"], {"state": "assigned", "assigned_aircraft_id": aircraft["id"], "mission_id": mission_id})
        store.append(
            "MISSION_LAUNCHED",
            "mission",
            mission_id,
            {"order_id": order["id"], "aircraft_id": aircraft["id"], "launched_at": state["clock"], "eta": eta},
        )
    return fold(store.list())


def inject_storm(store: EventStore) -> dict[str, Any]:
    state = fold(store.list())
    store.append("NEST_WEATHER_SET", "nest", "NEST-01", {"weather_state": "storm_front", "status": "degraded"})
    groundable = [a for a in state["fleet"] if a["state"] not in {"grounded", "maintenance"}]
    to_ground_count = max(0, len(groundable) - 2)
    active_by_aircraft = {mission["aircraft_id"]: mission for mission in state["active_missions"]}
    for aircraft in groundable[:to_ground_count]:
        grounded_until = state["clock"] + 30
        mission = active_by_aircraft.get(aircraft["id"])
        if mission:
            store.append(
                "MISSION_ABORTED",
                "mission",
                mission["id"],
                {
                    "order_id": mission["order_id"],
                    "aircraft_id": aircraft["id"],
                    "aborted_at": state["clock"],
                    "reason": "storm front forced aircraft down",
                    "grounded_until": grounded_until,
                },
            )
        else:
            store.append(
                "AIRCRAFT_STATUS_SET",
                "aircraft",
                aircraft["id"],
                {"state": "grounded", "current_mission_id": None, "charge_complete_at": None, "grounded_until": grounded_until},
            )
    store.append("SCENARIO_INJECTED", "scenario", "storm-front", {"name": "Storm front grounded fleet to two operational aircraft."})
    return fold(store.list())


def inject_aircraft_down(store: EventStore) -> dict[str, Any]:
    state = fold(store.list())
    candidates = [a for a in state["fleet"] if a["state"] in {"ready", "charging", "grounded"}]
    if candidates:
        aircraft = sorted(candidates, key=lambda a: a["id"])[0]
        store.append("AIRCRAFT_STATUS_SET", "aircraft", aircraft["id"], {"state": "maintenance", "maintenance_reason": "motor vibration"})
        store.append("SCENARIO_INJECTED", "scenario", "aircraft-down", {"name": f"{aircraft['id']} moved to maintenance."})
    return fold(store.list())


def inject_demand_spike(store: EventStore) -> dict[str, Any]:
    state = fold(store.list())
    start = len(state["orders"]) + 1
    batch = ["emergency blood", "time-critical biologics", "vaccines", "prescriptions", "retail", "food", "food", "retail"]
    for idx, vertical in enumerate(batch, start=start):
        tier = tier_for(vertical)
        promised = state["clock"] + (24 if tier == "P0" else 42 if tier == "P1" else 70)
        store.append(
            "ORDER_CREATED",
            "order",
            f"O-{idx:03d}",
            {
                "vertical": vertical,
                "priority_tier": tier,
                "payload_kg": 1.2 + (idx % 4) * 0.25,
                "created_at": state["clock"],
                "promised_by": promised,
                "destination": "Mercy Hospital" if tier == "P0" else "Downtown Zone",
                "urgency_flag": tier == "P0",
                "state": "pending",
            },
        )
    store.append("SCENARIO_INJECTED", "scenario", "demand-spike", {"name": "Hospital emergency batch plus lunch surge."})
    return fold(store.list())


def apply_triage(store: EventStore, operator: str = "ops-console") -> dict[str, Any]:
    state = fold(store.list())
    triage = make_triage(state)
    for action in ("defer", "ground_fallback"):
        for item in triage["plan"][action]:
            if item.get("committed"):
                continue
            order = state_order(state, item["order_id"])
            if order["priority_tier"] == "P0" and action == "defer":
                continue
            target_state = "deferred" if action == "defer" else action
            store.append("ORDER_STATE_SET", "order", order["id"], {"state": target_state})
            store.append(
                "INTERVENTION_RECORDED",
                "intervention",
                order["id"],
                {"type": "triage_apply", "order_id": order["id"], "operator": operator, "reason": item["rationale"], "target_action": target_state},
                actor=operator,
            )
    return fold(store.list())


def override_order(store: EventStore, order_id: str, target_action: str, operator: str, reason: str) -> dict[str, Any]:
    if not operator.strip() or not reason.strip():
        raise ValueError("operator and reason are required")
    state = fold(store.list())
    order = state_order(state, order_id)
    if order["priority_tier"] == "P0" and target_action == "deferred" and len(reason.strip()) < 12:
        raise ValueError("P0 deferral override requires an explicit reason")
    if target_action not in {"pending", "deferred", "ground_fallback", "failed"}:
        raise ValueError("unsupported override target")
    store.append("ORDER_STATE_SET", "order", order_id, {"state": target_action}, actor=operator)
    store.append(
        "INTERVENTION_RECORDED",
        "intervention",
        order_id,
        {"type": "manual_override", "order_id": order_id, "operator": operator, "reason": reason, "target_action": target_action},
        actor=operator,
    )
    return fold(store.list())


def timeline(store: EventStore, order_id: str) -> list[dict[str, Any]]:
    events = store.list()
    related_missions = {e.entity_id for e in events if e.type == "MISSION_LAUNCHED" and e.payload.get("order_id") == order_id}
    result = [
        e
        for e in events
        if (e.entity_type == "order" and e.entity_id == order_id)
        or (e.entity_type == "intervention" and e.entity_id == order_id)
        or (e.entity_type == "mission" and e.entity_id in related_missions)
    ]
    clock = 0
    out = []
    for event in events:
        if event.type == "CLOCK_SET":
            clock = int(event.payload["minute"])
        elif event.type == "CLOCK_ADVANCED":
            clock += int(event.payload.get("minutes", 1))
        if event in result:
            out.append(event_to_dict(event, clock))
    return out


def audit(store: EventStore) -> list[dict[str, Any]]:
    state = fold(store.list())
    return sorted(state["interventions"], key=lambda item: item["id"], reverse=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
