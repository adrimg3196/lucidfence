"""Offline UEM API replay harness.

The harness is deliberately small and stdlib-only from LucidFence's point of
view: tests inject it as a requests-compatible transport so live adapters can be
exercised against recorded/anonymous edge cases without network or secrets.
"""
from __future__ import annotations

from collections.abc import Mapping
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
    headers: Mapping[str, str] = field(default_factory=dict)

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
    raw = headers.get("Retry-After") if isinstance(headers, Mapping) else None
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


def _page_payload(adapter: str, rows: list[dict], next_url: str | None = None) -> dict:
    if adapter == "jamf":
        payload: dict[str, Any] = {"results": rows}
        if next_url:
            payload["links"] = {"next": next_url}
        return payload
    payload = {"value": rows}
    if next_url:
        payload["@odata.nextLink"] = next_url
    return payload


def _replay_adapter_result(adapter: str, responses: list[ReplayResponse]) -> tuple[dict, ReplayTransport, ReplayClock]:
    clock = ReplayClock()
    transport = ReplayTransport(adapter, responses, clock=clock)
    if adapter == "intune":
        from lucidfence.core.adapters.intune import IntuneAdapter

        runner = IntuneAdapter(
            live=True,
            tenant_id="replay-tenant",
            client_id="replay-client",
            client_secret="replay-secret",
            endpoint_template="https://graph.replay",
        )
    elif adapter == "jamf":
        from lucidfence.core.adapters.jamf import JamfAdapter

        runner = JamfAdapter(
            live=True,
            base_url="https://jamf.replay",
            client_id="replay-client",
            client_secret="replay-secret",
        )
    else:
        raise ValueError(f"unsupported replay adapter: {adapter}")
    runner._token = "replay-token"
    runner._token_expires_at = float("inf")
    runner.requests = transport
    result = runner.execute({"device_id": ""}, "list", {})
    return result, transport, clock


def _scenario_responses(adapter: str, scenario: str) -> list[ReplayResponse]:
    if scenario in {"unknown_payload", "clock_skew"}:
        return [ReplayResponse(200, _fixture_payload(adapter, scenario))]
    if scenario == "pagination":
        first_url = "https://jamf.replay/page-2" if adapter == "jamf" else "https://graph.replay/page-2"
        return [
            ReplayResponse(200, _page_payload(adapter, [{"id": f"{adapter}-page-1"}], first_url)),
            ReplayResponse(200, _page_payload(adapter, [{"id": f"{adapter}-page-2"}])),
        ]
    if scenario == "duplicate_cursor":
        repeated_url = "https://jamf.replay/repeated" if adapter == "jamf" else "https://graph.replay/repeated"
        return [
            ReplayResponse(200, _page_payload(adapter, [{"id": f"{adapter}-dup-1"}], repeated_url)),
            ReplayResponse(200, _page_payload(adapter, [{"id": f"{adapter}-dup-2"}], repeated_url)),
        ]
    if scenario == "rate_limit_retry_after":
        return [
            ReplayResponse(429, {"error": "slow down"}, headers={"Retry-After": "2"}),
            ReplayResponse(200, _page_payload(adapter, [])),
        ]
    if scenario == "auth_errors":
        return [ReplayResponse(401, {"error": "denied"}, text="denied")]
    if scenario == "timeout":
        return []
    if scenario == "partial_json":
        return [ReplayResponse(200, None, text="{partial")]
    raise ValueError(f"unknown replay scenario: {scenario}")


def _scenario_status(scenario: str, result: dict) -> str:
    if scenario == "clock_skew":
        return "unknown" if result.get("ok") else "error"
    if scenario == "duplicate_cursor":
        return "degraded" if result.get("error_type") == "duplicate_cursor" else "error"
    if scenario == "auth_errors":
        return "supported" if result.get("error_type") == "auth_error" else "error"
    if scenario == "timeout":
        return "error" if result.get("ok") is False else "supported"
    if scenario == "partial_json":
        return "unknown" if result.get("error_type") == "invalid_payload" else "error"
    return "supported" if result.get("ok") else "error"


def run_inventory_replay_matrix() -> dict:
    """Generate the offline coverage matrix for declared inventory adapters.

    Status vocabulary is intentionally bounded to the issue contract:
    supported/degraded/unknown/error. A new inventory-capable adapter must either
    be represented here or declare a documented exception; otherwise this matrix
    reports it under ``uncovered_inventory_adapters`` so CI fails.
    """

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
            for scenario in (
                "unknown_payload",
                "clock_skew",
                "pagination",
                "duplicate_cursor",
                "rate_limit_retry_after",
                "auth_errors",
                "timeout",
                "partial_json",
            ):
                responses = _scenario_responses(name, scenario)
                fixture_payload = responses[0].body if responses else {}
                result, transport, clock = _replay_adapter_result(name, responses)
                scenarios[scenario] = {
                    "status": _scenario_status(scenario, result),
                    "unknown_fields": _unknown_fields(fixture_payload) if isinstance(fixture_payload, dict) else [],
                    "preserved_payload": fixture_payload,
                    "adapter_result": result,
                    "replay_calls": transport.calls,
                    "virtual_sleeps": clock.sleeps,
                }
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
