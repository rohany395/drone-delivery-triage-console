from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.engine import EventStore, apply_triage, check_invariants, fold, make_triage, override_order, seed, timeline
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
