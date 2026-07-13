"""Incident lifecycle tests: persistent, tenant-local and auditable."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_incident_lifecycle_persists_and_records_audit():
    from core.incidents import IncidentStore

    with tempfile.TemporaryDirectory() as td:
        store = IncidentStore(Path(td))
        derived = [{
            "id": "inc-outside-dev-1", "type": "geofence_exit", "severity": "high",
            "status": "open", "title": "Fuera", "device_id": "dev-1",
            "device_name": "Tablet", "first_seen": "2026-07-10T10:00:00+00:00",
            "last_seen": "2026-07-10T10:00:00+00:00", "count": 1,
        }]
        rows = store.merge(derived)
        assert rows[0]["status"] == "open"

        updated = store.transition(
            "inc-outside-dev-1", "acknowledged", actor="usr-1",
            assignee="soc@acme.test", note="Investigando",
        )
        assert updated["status"] == "acknowledged"
        assert updated["assignee"] == "soc@acme.test"
        assert updated["acknowledged_at"]
        assert updated["timeline"][-1]["from"] == "open"
        assert updated["timeline"][-1]["to"] == "acknowledged"
        assert updated["timeline"][-1]["actor"] == "usr-1"

        reloaded = IncidentStore(Path(td)).merge(derived)[0]
        assert reloaded["status"] == "acknowledged"
        assert reloaded["assignee"] == "soc@acme.test"

        resolved = IncidentStore(Path(td)).transition(
            "inc-outside-dev-1", "resolved", actor="usr-2", note="Dispositivo recuperado"
        )
        assert resolved["status"] == "resolved"
        assert resolved["resolved_at"]
        assert len(resolved["timeline"]) == 2


def test_incident_invalid_transition_is_rejected():
    from core.incidents import IncidentStore

    with tempfile.TemporaryDirectory() as td:
        store = IncidentStore(Path(td))
        store.merge([{"id": "inc-1", "status": "open", "title": "x"}])
        try:
            store.transition("inc-1", "invalid", actor="usr-1")
            assert False, "invalid status should fail"
        except ValueError as exc:
            assert "estado" in str(exc).lower()


def test_resolved_incident_reopens_when_risk_reappears_only_when_requested():
    from core.incidents import IncidentStore

    with tempfile.TemporaryDirectory() as td:
        store = IncidentStore(Path(td))
        derived = [{"id": "inc-1", "status": "open", "title": "x", "last_seen": "t1"}]
        store.merge(derived)
        store.transition("inc-1", "resolved", actor="usr-1")
        still_resolved = store.merge([{**derived[0], "last_seen": "t2"}])[0]
        assert still_resolved["status"] == "resolved"
        reopened = store.transition("inc-1", "open", actor="usr-1", note="Reincidencia")
        assert reopened["status"] == "open"
        assert reopened["resolved_at"] is None
