from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.evidence_export import build_evidence_report
from lucidfence.core.export import export_compliance_csv, export_inventory_csv
from lucidfence.core.location_source import LiveLocationSource, LocationReport
from lucidfence.core.policies import Policy, RiskEngine
from helpers import make_temp_engine


class _OneReportSource:
    def __init__(self, report: LocationReport):
        self.report = report
        self.last_error = None

    def fetch(self):
        return [self.report]


def test_freshness_classifies_ttl_edge_future_replay_missing_nonce_and_unverifiable() -> None:
    from lucidfence.core.evidence_freshness import EvidenceFreshnessVerifier, ReplayRegistry

    with tempfile.TemporaryDirectory() as td:
        registry = ReplayRegistry(os.path.join(td, "replay.json"), max_entries=3, retention_seconds=600)
        verifier = EvidenceFreshnessVerifier(
            {"location": {"ttl_seconds": 300, "require_nonce": True}},
            clock_skew_seconds=30,
            replay_registry=registry,
        )

        edge = verifier.evaluate(
            signal_type="location", source="applivery", observed_at="2026-09-02T12:00:00Z",
            evidence_ts="2026-09-02T11:55:00Z", nonce="n-edge",
        )
        assert edge["status"] == "fresh"
        assert edge["age_seconds"] == 300
        assert edge["rule"] == "ttl=300s skew=30s nonce=required"
        assert "applivery" in edge["reason"] and "300s" in edge["reason"]

        stale = verifier.evaluate(
            signal_type="location", source="applivery", observed_at="2026-09-02T12:00:01Z",
            evidence_ts="2026-09-02T11:55:00Z", nonce="n-stale",
        )
        assert stale["status"] == "stale"
        assert stale["age_seconds"] == 301

        future = verifier.evaluate(
            signal_type="location", source="applivery", observed_at="2026-09-02T12:00:00Z",
            evidence_ts="2026-09-02T12:00:31Z", nonce="n-future",
        )
        assert future["status"] == "future"
        assert future["age_seconds"] == -31

        replay = verifier.evaluate(
            signal_type="location", source="applivery", observed_at="2026-09-02T12:01:00Z",
            evidence_ts="2026-09-02T12:00:00Z", nonce="n-edge",
        )
        assert replay["status"] == "replayed"

        missing_nonce = verifier.evaluate(
            signal_type="location", source="applivery", observed_at="2026-09-02T12:00:00Z",
            evidence_ts="2026-09-02T11:59:00Z", nonce=None,
        )
        assert missing_nonce["status"] == "unverifiable"
        assert missing_nonce["age_seconds"] == 60

        no_clock = verifier.evaluate(
            signal_type="location", source="legacy-uem", observed_at="2026-09-02T12:00:00Z",
            evidence_ts=None, nonce="n-clockless",
        )
        assert no_clock["status"] == "unverifiable"
        assert no_clock["age_seconds"] is None


def test_replay_registry_prunes_by_retention_and_size_deterministically() -> None:
    from lucidfence.core.evidence_freshness import ReplayRegistry

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "replay.json")
        registry = ReplayRegistry(path, max_entries=2, retention_seconds=100)
        assert registry.record("location", "n-old", observed_at="2026-09-02T11:58:00Z") is False
        assert registry.record("location", "n-a", observed_at="2026-09-02T12:00:00Z") is False
        assert registry.record("location", "n-b", observed_at="2026-09-02T12:00:01Z") is False
        assert registry.record("location", "n-c", observed_at="2026-09-02T12:00:02Z") is False

        data = json.loads(open(path, encoding="utf-8").read())
        assert [row["nonce"] for row in data["entries"]] == ["n-b", "n-c"]
        assert registry.record("location", "n-c", observed_at="2026-09-02T12:00:03Z") is True


def test_fresh_evidence_policy_condition_blocks_stale_without_turning_unknown_false() -> None:
    risk = {"risk_score": 90, "severity": "critical", "signals": {}}
    policy = Policy(
        id="p-lock-fresh", name="lock only with fresh location evidence", description="",
        when=[
            {"field": "risk_score", "op": "gte", "value": 80},
            {"field": "evidence_freshness:location.status", "op": "eq", "value": "fresh"},
        ],
        actions=[{"action": "lock"}], severity="critical",
    )
    engine = RiskEngine()
    fresh = {"device_id": "d1", "evidence_freshness": {"location": {"status": "fresh"}}}
    stale = {"device_id": "d1", "evidence_freshness": {"location": {"status": "stale"}}}
    unknown = {"device_id": "d1"}

    assert engine.match_policies([policy], risk, fresh, "outside")
    assert engine.match_policies([policy], risk, stale, "outside") == []
    assert engine.match_policies([policy], risk, unknown, "outside") == []
    assert unknown.get("compliant") is None


def test_run_once_downgrades_non_fresh_location_before_geofence_decisions() -> None:
    eng = make_temp_engine(extra_config={
        "evidence_freshness": {"signals": {"location": {"ttl_seconds": 300}}},
    })
    eng.add_fence({
        "id": "restricted", "name": "Restricted", "type": "circle",
        "center": {"lat": 40.5, "lng": -3.7}, "radius_m": 300,
        "actions": [{"action": "lock", "when": "on_enter", "params": {}}],
    })
    eng.source = _OneReportSource(LocationReport(
        device_id="stale-loc", name="Stale Loc", platform="ios", status="active",
        compliant=False, lat=40.5, lng=-3.7, last_seen="2026-09-02T12:00:00Z",
        location_source="applivery", evidence_ts="2000-01-01T00:00:00Z",
    ))

    eng.run_once()

    ds = eng.store.snapshot()["stale-loc"]
    assert ds.evidence_freshness["location"]["status"] == "stale"
    assert ds.fence_state == "unknown"
    assert ds.inside_fence is None
    assert ds.route_state == "unassigned"
    assert eng._cycle_actions == []


def test_applivery_location_evidence_ts_comes_only_from_location_timestamp() -> None:
    report = LiveLocationSource(org_id="org-test")._to_report({
        "id": "dev-no-loc-clock",
        "type": "ios",
        "lastStatusReportTime": "2026-09-02T12:00:00Z",
        "sortDate": "2026-09-02T12:00:01Z",
        "lastLocation": {"agent": {"latitude": 40.5, "longitude": -3.7}},
    })

    assert report.lat == 40.5
    assert report.lng == -3.7
    assert report.last_seen == "2026-09-02T12:00:00Z"
    assert report.last_checkin == "2026-09-02T12:00:01Z"
    assert report.evidence_ts is None


def test_corrupt_replay_registry_makes_nonce_evidence_unverifiable() -> None:
    from lucidfence.core.evidence_freshness import EvidenceFreshnessVerifier, ReplayRegistry

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "replay.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        verifier = EvidenceFreshnessVerifier(
            {"location": {"ttl_seconds": 300}},
            replay_registry=ReplayRegistry(path),
        )

        result = verifier.evaluate(
            signal_type="location", source="applivery", observed_at="2026-09-02T12:00:00Z",
            evidence_ts="2026-09-02T11:59:00Z", nonce="n-corrupt",
        )

        assert result["status"] == "unverifiable"
        assert "registro replay" in result["reason"]
        with open(path, encoding="utf-8") as fh:
            assert fh.read() == "{not json"


def test_api_export_and_evidence_report_keep_unknown_freshness_separate() -> None:
    device = {
        "device_id": "d-unknown", "name": "No clock", "platform": "android",
        "compliant": None, "fence_state": "unknown", "inside_fence": None,
        "risk_score": None, "risk_severity": "unknown", "os_version": "Android",
        "last_checkin": "2026-09-02T11:00:00Z",
        "evidence_freshness": {"location": {"status": "unverifiable", "source": "legacy-uem", "age_seconds": None,
            "rule": "ttl=300s skew=30s nonce=optional", "reason": "legacy-uem sin reloj confiable"}},
    }

    inventory = export_inventory_csv([device])
    compliance = export_compliance_csv([device])
    assert "evidence_freshness_location_status" in inventory
    assert "unverifiable" in inventory
    assert "evidence_freshness_location_status" in compliance
    assert "False" not in compliance.splitlines()[1].split(",")

    report = build_evidence_report(org="o", devices=[device], events=[], actions=[], generated_at="2026-09-02T12:00:00Z")
    rec = report["records"][0]
    assert rec["evidence_freshness"]["location"]["status"] == "unverifiable"
    assert rec["compliant"] is None
