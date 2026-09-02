"""Offline replay fixtures for UEM API edge cases (issue #236).

The suite runs without network or secrets and exercises every inventory-capable
adapter that advertises live inventory coverage. Fixtures intentionally include
pagination, duplicate cursors, 429 Retry-After, partial JSON, unknown fields, and
clock skew.
"""
from __future__ import annotations

from collections.abc import Mapping

import sys
sys.path.insert(0, ".")

from lucidfence.core.adapters.capabilities import capability_for
from lucidfence.core.adapters.replay import (
    ReplayClock,
    ReplayResponse,
    ReplayTransport,
    run_inventory_replay_matrix,
)
from lucidfence.core.adapters.intune import IntuneAdapter


class _CaseInsensitiveHeaders(Mapping):
    def __init__(self, values):
        self._values = {str(k).lower(): v for k, v in values.items()}

    def __getitem__(self, key):
        return self._values[str(key).lower()]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def get(self, key, default=None):
        return self._values.get(str(key).lower(), default)


class _RequestsProxy:
    def __init__(self, transport: ReplayTransport):
        self.transport = transport
        self.RequestException = RuntimeError

    def get(self, url, **kwargs):
        return self.transport.get(url, **kwargs)

    def post(self, url, **kwargs):
        return self.transport.post(url, **kwargs)

    def patch(self, url, **kwargs):
        return self.transport.patch(url, **kwargs)


def test_retry_after_uses_injected_clock_without_real_sleep():
    clock = ReplayClock()
    transport = ReplayTransport(
        "intune",
        [
            ReplayResponse(429, {"error": "slow down"}, headers=_CaseInsensitiveHeaders({"retry-after": "3"})),
            ReplayResponse(200, {"value": []}),
        ],
        clock=clock,
    )
    adapter = IntuneAdapter(live=True, tenant_id="t", client_id="c", client_secret="s")
    adapter._token = "token"
    adapter._token_expires_at = float("inf")
    adapter.requests = _RequestsProxy(transport)

    out = adapter.execute({"device_id": ""}, "list", {})

    assert out["ok"] is True
    assert out["replay"]["rate_limited"] == 1
    assert clock.sleeps == [3.0]
    assert transport.calls == 2


def test_duplicate_cursor_stops_without_infinite_loop_or_silent_loss():
    clock = ReplayClock()
    transport = ReplayTransport(
        "intune",
        [
            ReplayResponse(200, {"value": [{"id": "a", "deviceName": "A"}], "@odata.nextLink": "https://graph.test/page-2"}),
            ReplayResponse(200, {"value": [{"id": "b", "deviceName": "B"}], "@odata.nextLink": "https://graph.test/page-2"}),
        ],
        clock=clock,
    )
    adapter = IntuneAdapter(live=True, tenant_id="t", client_id="c", client_secret="s", endpoint_template="https://graph.test")
    adapter._token = "token"
    adapter._token_expires_at = float("inf")
    adapter.requests = _RequestsProxy(transport)

    out = adapter.execute({"device_id": ""}, "list", {})

    assert out["ok"] is False, out
    assert out["error_type"] == "duplicate_cursor", out
    assert out["replay"]["partial_count"] == 2
    assert transport.calls == 2


def test_replay_matrix_marks_unknowns_and_fails_uncovered_inventory_adapters():
    matrix = run_inventory_replay_matrix()

    assert matrix["ok"] is True, matrix
    assert matrix["network"] == "offline"
    covered = {row["adapter"]: row for row in matrix["results"]}
    for adapter_name in ("intune", "jamf"):
        assert capability_for(adapter_name).inventory is True
        assert covered[adapter_name]["status"] in {"supported", "degraded", "unknown", "error"}
        assert covered[adapter_name]["scenarios"]["unknown_payload"]["unknown_fields"]
        assert covered[adapter_name]["scenarios"]["clock_skew"]["status"] == "unknown"
        for scenario_name, scenario in covered[adapter_name]["scenarios"].items():
            if scenario_name == "documented_exception":
                continue
            assert scenario["replay_calls"] > 0, (adapter_name, scenario_name, scenario)
            assert scenario["adapter_result"]["adapter"] == adapter_name
    assert matrix["uncovered_inventory_adapters"] == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
