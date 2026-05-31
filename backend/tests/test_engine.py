from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.engine import EventStore, apply_triage, check_invariants, fold, inject_storm, make_triage, override_order, seed, tick, timeline
from app.main import app


def make_store(tmp_path: Path) -> EventStore:
    store = EventStore(tmp_path / "events.sqlite")
    seed(store)
    return store


def test_seed_is_deterministic(tmp_path: Path):
    store = make_store(tmp_path)
    state = fold(store.list())
    assert state["clock"] == 0
    assert len(state["fleet"]) == 6
    assert len(state["orders"]) == 24
    assert all(check["ok"] for check in state["invariants"])


def test_priority_ordering_respects_tiers_and_sla(tmp_path: Path):
    store = make_store(tmp_path)
    state = fold(store.list())
    ranked = [o for o in state["orders"] if o["state"] == "pending"]
    assert ranked[0]["priority_tier"] == "P0"
    p0_promises = [o["promised_by"] for o in ranked if o["priority_tier"] == "P0"]
    assert p0_promises == sorted(p0_promises)


def test_triage_never_auto_defers_p0(tmp_path: Path):
    store = make_store(tmp_path)
    state = fold(store.list())
    triage = make_triage(state)
    deferred_ids = {item["order_id"] for item in triage["plan"]["defer"]}
    p0_ids = {o["id"] for o in state["orders"] if o["priority_tier"] == "P0"}
    assert deferred_ids.isdisjoint(p0_ids)


def test_override_requires_reason_and_actor(tmp_path: Path):
    store = make_store(tmp_path)
    with pytest.raises(ValueError):
        override_order(store, "O-003", "deferred", "", "")
    state = override_order(store, "O-003", "deferred", "Rohan", "Customer requested ground handoff.")
    assert any(item["type"] == "manual_override" for item in state["interventions"])


def test_no_double_assignment_invariant_catches_invalid_state(tmp_path: Path):
    store = make_store(tmp_path)
    store.append("MISSION_LAUNCHED", "mission", "M-X1", {"order_id": "O-001", "aircraft_id": "Z-01", "launched_at": 0, "eta": 20})
    store.append("MISSION_LAUNCHED", "mission", "M-X2", {"order_id": "O-002", "aircraft_id": "Z-01", "launched_at": 0, "eta": 20})
    state = fold(store.list())
    check = next(item for item in state["invariants"] if item["name"] == "No double-assignment")
    assert check["ok"] is False


def test_no_lost_orders_invariant_catches_dropped_folded_order(tmp_path: Path):
    store = make_store(tmp_path)
    events = store.list()
    state = fold(events)
    state["orders"] = [order for order in state["orders"] if order["id"] != "O-001"]
    check = next(item for item in check_invariants(state, events) if item["name"] == "No lost orders")
    assert check["ok"] is False
    assert "O-001" in check["detail"]


def test_p0_protection_allows_logged_override_and_blocks_silent_deferral(tmp_path: Path):
    authorized = make_store(tmp_path / "authorized")
    authorized_state = override_order(authorized, "O-001", "deferred", "Rohan", "Hospital requested ground clinical courier.")
    authorized_check = next(item for item in authorized_state["invariants"] if item["name"] == "P0 protection")
    assert authorized_check["ok"] is True

    unauthorized = make_store(tmp_path / "unauthorized")
    unauthorized.append("ORDER_STATE_SET", "order", "O-001", {"state": "deferred"})
    unauthorized_state = fold(unauthorized.list())
    unauthorized_check = next(item for item in unauthorized_state["invariants"] if item["name"] == "P0 protection")
    assert unauthorized_check["ok"] is False
    assert "O-001" in unauthorized_check["detail"]


def test_storm_at_clock_zero_constrains_capacity_and_preserves_invariants(tmp_path: Path):
    store = make_store(tmp_path)
    state = inject_storm(store)
    assert state["metrics"]["capacity_tight"] is True
    assert state["metrics"]["operational_aircraft"] <= 2
    assert all(check["ok"] for check in state["invariants"])

    ticked = tick(store)
    assert ticked["metrics"]["capacity_tight"] is True
    assert all(check["ok"] for check in ticked["invariants"])


def test_storm_after_ticks_aborts_flights_and_preserves_invariants(tmp_path: Path):
    store = make_store(tmp_path)
    for _ in range(5):
        tick(store)

    before_storm = fold(store.list())
    assert before_storm["active_missions"]

    storm = inject_storm(store)
    assert storm["metrics"]["capacity_tight"] is True
    assert storm["metrics"]["operational_aircraft"] <= 2
    assert len(storm["active_missions"]) <= 2
    assert any(mission["state"] == "aborted" for mission in storm["missions"].values())
    assert all(check["ok"] for check in storm["invariants"])

    ticked = tick(store)
    assert ticked["metrics"]["capacity_tight"] is True
    assert all(check["ok"] for check in ticked["invariants"])


def test_storm_does_not_freeze_p0_delivery(tmp_path: Path):
    store = make_store(tmp_path)
    inject_storm(store)
    apply_triage(store, "Rohan")
    before = {o["id"] for o in fold(store.list())["orders"] if o["priority_tier"] == "P0" and o["state"] == "pending"}
    for _ in range(12):
        tick(store)
    state = fold(store.list())
    after = {o["id"] for o in state["orders"] if o["priority_tier"] == "P0" and o["state"] == "pending"}
    assert after < before
    assert all(c["ok"] for c in state["invariants"])


def test_storm_recovers_and_clears(tmp_path: Path):
    store = make_store(tmp_path)
    assert inject_storm(store)["nest"]["weather_state"] == "storm_front"
    for _ in range(40):
        tick(store)
    state = fold(store.list())
    assert state["nest"]["weather_state"] == "nominal"
    assert not any(o["priority_tier"] == "P0" and o["state"] == "pending" for o in state["orders"])
    assert all(c["ok"] for c in state["invariants"])


def test_deferred_orders_resume_after_recovery(tmp_path: Path):
    store = make_store(tmp_path)
    inject_storm(store)
    apply_triage(store, "Rohan")
    for _ in range(40):
        tick(store)
    state = fold(store.list())
    assert not any(o["state"] == "deferred" for o in state["orders"])
    assert all(c["ok"] for c in state["invariants"])


def test_triage_includes_committed_override_in_target_column_only(tmp_path: Path):
    store = make_store(tmp_path)
    storm = inject_storm(store)
    protected_order_id = storm["orders"][0]["id"]

    override_order(store, protected_order_id, "ground_fallback", "Rohan", "Operator moved this order to ground courier.")
    triage = make_triage(fold(store.list()))

    locations = [
        column
        for column, items in triage["plan"].items()
        if any(item["order_id"] == protected_order_id for item in items)
    ]
    committed_item = next(item for item in triage["plan"]["ground_fallback"] if item["order_id"] == protected_order_id)

    assert locations == ["ground_fallback"]
    assert triage["plan"]["ground_fallback"][0]["order_id"] == protected_order_id
    assert committed_item["committed"] is True
    assert committed_item["rationale"] == "Moved by operator override."


def test_timeline_reconstructs_order_history(tmp_path: Path):
    store = make_store(tmp_path)
    override_order(store, "O-003", "ground_fallback", "Rohan", "Protecting medical launch capacity.")
    events = timeline(store, "O-003")
    assert [event["type"] for event in events] == ["ORDER_CREATED", "ORDER_STATE_SET", "INTERVENTION_RECORDED"]


def test_apply_triage_creates_audit_visible_events(tmp_path: Path):
    store = make_store(tmp_path)
    state = apply_triage(store, "ops")
    assert state["interventions"]
    assert all(item["operator"] == "ops" for item in state["interventions"])


def test_api_reset_and_scenarios():
    client = TestClient(app)
    reset = client.post("/api/sim/reset")
    assert reset.status_code == 200
    before = reset.json()["metrics"]["operational_aircraft"]
    storm = client.post("/api/scenarios/storm-front")
    assert storm.status_code == 200
    assert storm.json()["metrics"]["operational_aircraft"] < before
    spike = client.post("/api/scenarios/demand-spike")
    assert spike.status_code == 200
    assert spike.json()["metrics"]["backlog"] >= reset.json()["metrics"]["backlog"]
    triage = client.get("/api/triage").json()
    assert "fifo_baseline" in triage
