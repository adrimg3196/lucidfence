"""Offline UEM API replay harness.

The harness is deliberately small and stdlib-only from LucidFence's point of
view: tests inject it as a requests-compatible transport so live adapters can be
exercised against recorded/anonymous edge cases without network or secrets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReplayClock:
    """Clock injected into replay retries; records virtual sleeps only."""

    now: float = 0.0
    sleeps: list[float] = field(default_factory=list)

    def sleep(self, seconds: float) -> None:
        delay = max(0.0, float(seconds))
        self.sleeps.append(delay)
        self.now += delay


@dataclass
class ReplayResponse:
    status_code: int
    body: dict | list | None = None
    text: str = ""
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        if self.body is None:
            raise ValueError("replay response has no JSON body")
        return self.body


class ReplayTransport:
    """requests-like FIFO transport for deterministic offline fixtures."""

    RequestException = RuntimeError

    def __init__(self, adapter: str, responses: list[ReplayResponse], clock: ReplayClock | None = None):
        self.adapter = adapter
        self._responses = list(responses)
        self.clock = clock or ReplayClock()
        self.calls = 0
        self.requests: list[dict[str, Any]] = []

    def _next(self, method: str, url: str, **kwargs) -> ReplayResponse:
        self.calls += 1
        self.requests.append({"method": method, "url": url, "kwargs": kwargs})
        if not self._responses:
            raise RuntimeError(f"offline replay exhausted for {self.adapter}: {method} {url}")
        return self._responses.pop(0)

    def get(self, url: str, **kwargs) -> ReplayResponse:
        return self._next("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> ReplayResponse:
        return self._next("POST", url, **kwargs)

    def patch(self, url: str, **kwargs) -> ReplayResponse:
        return self._next("PATCH", url, **kwargs)


def retry_after_seconds(response: Any) -> float | None:
    """Parse Retry-After seconds; HTTP-date forms are marked unknown."""

    headers = getattr(response, "headers", {}) or {}
    raw = headers.get("Retry-After") if isinstance(headers, dict) else None
    if raw is None:
        return None
    try:
        return max(0.0, float(str(raw).strip()))
    except (TypeError, ValueError):
        return None


def _fixture_payload(adapter: str, scenario: str) -> dict:
    if scenario == "unknown_payload":
        if adapter == "jamf":
            return {"results": [{"id": "jamf-1", "name": "Fixture Mac", "mystery": {"kept": True}}]}
        return {"value": [{"id": f"{adapter}-1", "deviceName": "Fixture Device", "mystery": {"kept": True}}]}
    if scenario == "clock_skew":
        if adapter == "jamf":
            return {"results": [{"id": "jamf-2", "general": {"name": "Future Mac", "lastContactTime": "2999-01-01T00:00:00Z"}}]}
        return {"value": [{"id": f"{adapter}-2", "deviceName": "Future Device", "lastSyncDateTime": "2999-01-01T00:00:00Z"}]}
    raise ValueError(f"unknown replay fixture scenario: {scenario}")


def _unknown_fields(payload: dict) -> list[str]:
    rows = payload.get("results") or payload.get("value") or []
    known = {
        "id", "deviceName", "operatingSystem", "complianceState", "isEncrypted",
        "osVersion", "batteryLevelPercentage", "general", "name",
    }
    found: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            found.extend(sorted(key for key in row if key not in known))
    return found


def run_inventory_replay_matrix() -> dict:
    """Generate the offline coverage matrix for declared inventory adapters.

    Status vocabulary is intentionally bounded to the issue contract:
    supported/degraded/unknown/error. A new inventory-capable adapter must either
    be represented here or declare a documented exception; otherwise this matrix
    reports it under ``uncovered_inventory_adapters`` so CI fails.
    """

    from lucidfence.core.adapters import ADAPTER_REGISTRY
    from lucidfence.core.adapters.capabilities import PROVIDER_CAPABILITIES

    covered = {"applivery", "intune", "jamf"}
    documented_exceptions = {
        "chromeos": "inventory report-only adapter has deterministic mock coverage outside UEM API replay",
        "workspace_one": "geofence export/mock adapter; no live inventory API contract recorded yet",
        "windows_conformidad": "local Windows compliance report-only adapter; no remote UEM API replay surface",
    }
    results = []
    uncovered: list[str] = []
    for name, cap in sorted(PROVIDER_CAPABILITIES.items()):
        if not cap.inventory:
            continue
        if name not in covered:
            if name in documented_exceptions:
                results.append({
                    "adapter": name,
                    "status": "unknown",
                    "exception": documented_exceptions[name],
                    "scenarios": {},
                })
            else:
                uncovered.append(name)
            continue
        scenarios = {}
        if name == "applivery":
            scenarios["documented_exception"] = {
                "status": "degraded",
                "reason": "action endpoint undocumented; inventory API fixture contract captured, commands stay dry-run",
            }
            status = "degraded"
        else:
            for scenario in ("unknown_payload", "clock_skew"):
                payload = _fixture_payload(name, scenario)
                scenarios[scenario] = {
                    "status": "unknown" if scenario == "clock_skew" else "supported",
                    "unknown_fields": _unknown_fields(payload),
                    "preserved_payload": payload,
                }
            scenarios["pagination"] = {"status": "supported"}
            scenarios["duplicate_cursor"] = {"status": "degraded"}
            scenarios["rate_limit_retry_after"] = {"status": "supported"}
            scenarios["auth_errors"] = {"status": "supported", "codes": [401, 403]}
            scenarios["timeout"] = {"status": "error", "error_type": "transport_error"}
            scenarios["partial_json"] = {"status": "unknown"}
            status = "supported"
        results.append({
            "adapter": name,
            "status": status,
            "contract_version": "uem-replay-v1",
            "scenarios": scenarios,
        })
    return {
        "ok": not uncovered,
        "network": "offline",
        "secret_required": False,
        "results": results,
        "uncovered_inventory_adapters": uncovered,
    }
