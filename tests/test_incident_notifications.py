"""TDD: incident webhook notifier (Slack/Teams) + MTTR analytics.

Two operational capabilities for a SOC-ready product:
  1. core/notifier.py -> POSTs an incident lifecycle event to a tenant
     webhook (Slack/Teams incoming-webhook shape). Stdlib only, never raises,
     records delivery result. Used for real-time alerting on new/ack/resolved.
  2. core/incidents.py analytics() -> MTTR (mean/median), open counts, by
     severity, and oldest-open age. Used by the dashboard MTTR panel.
"""
import os
import sys
import json
import time as _time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.notifier import IncidentNotifier  # noqa: E402
from core.incidents import IncidentStore  # noqa: E402


def _make_store(tmp: Path):
    return IncidentStore(tmp)


def test_notifier_posts_on_event_and_never_raises():
    sent = []

    def fake_post(url, payload):
        sent.append((url, payload))
        return {"ok": True, "status": 200}

    n = IncidentNotifier(webhook_url="https://hooks.slack.com/Test",
                         http_post=fake_post)
    ok = n.notify("open", {"id": "inc-1", "title": "Fuera de geocerca",
                            "severity": "high", "device_name": "Tablet A1"})
    assert ok is True
    assert len(sent) == 1
    url, payload = sent[0]
    assert url == "https://hooks.slack.com/Test"
    # Slack incoming-webhook shape
    assert "text" in payload and "Fuera de geocerca" in payload["text"]
    assert payload.get("attachments") or payload.get("blocks") or "text" in payload


def test_notifier_disabled_when_no_url():
    n = IncidentNotifier(webhook_url="")
    ok = n.notify("open", {"id": "x"})
    assert ok is False


def test_notifier_swallows_http_errors():
    def boom(url, payload):
        raise RuntimeError("network down")
    n = IncidentNotifier(webhook_url="https://x", http_post=boom)
    # must not raise
    assert n.notify("open", {"id": "x"}) is False


def test_notifier_fires_during_run_once_not_only_on_poll():
    """New incidents must notify at cycle time, independent of the dashboard."""
    import tempfile, config_loader
    from core.engine import Engine
    from core.location_source import LocationReport
    tmp = Path(tempfile.mkdtemp())
    sent = []
    def fake_post(url, payload):
        sent.append(payload)
        return {"ok": True, "status": 200}
    cfg = config_loader.load(Path("config.json"))
    cfg["data_dir"] = str(tmp)
    cfg["autostart"] = False
    cfg["incident_webhook_url"] = "https://hooks.slack.com/X"
    eng = Engine(cfg)
    eng.incidents.notifier._post = fake_post
    eng.routes = []
    eng.source = type("S", (), {"fetch": lambda self: [
        LocationReport(device_id="d1", name="Tabla1", platform="android",
                       status="active", compliant=False, lat=40.0, lng=-3.0)
    ]})()
    eng.run_once()
    # notification fired during the cycle itself
    assert len(sent) >= 1, "esperado >=1 delivery en run_once"
    assert any("fuera de geovalla" in (p.get("text") or "") or "no cumple" in (p.get("text") or "") for p in sent)
    tmp = Path(__import__("tempfile").mkdtemp())
    store = _make_store(tmp)
    now = _time.time()
    # Incident 1: opened at t0, resolved at t0+600 -> MTTR 600
    store.merge([{"id": "a", "type": "geofence_exit", "severity": "high",
                  "title": "A", "device_id": "d1", "device_name": "D1"}])
    store.transition("a", "acknowledged", actor="soc", note="seen")
    store.transition("a", "resolved", actor="soc", note="fixed")
    # Incident 2: opened, still open (no resolved_at)
    store.merge([{"id": "b", "type": "route_dev", "severity": "critical",
                  "title": "B", "device_id": "d2", "device_name": "D2"}])
    a = store.get("a")
    b = store.get("b")
    # backdate timeline timestamps to deterministic values (write through store)
    store._items["a"]["timeline"] = [
        {"ts": _iso(now - 600), "to": "open", "actor": "system"},
        {"ts": _iso(now), "to": "resolved", "actor": "soc"},
    ]
    store._items["b"]["timeline"] = [{"ts": _iso(now - 120), "to": "open", "actor": "system"}]
    store._persist()

    stats = store.analytics(now=_time.time)
    assert stats["open"] == 1, stats
    assert stats["resolved"] == 1, stats
    assert stats["by_severity"]["critical"] == 1, stats
    assert stats["by_severity"]["high"] == 1, stats
    # MTTR should be ~600s (open->resolved for 'a')
    assert 590 <= stats["mttr_seconds"] <= 610, stats
    assert stats["oldest_open_seconds"] >= 119, stats


def _iso(t):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()
