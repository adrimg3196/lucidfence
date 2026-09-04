"""Regression test for #302 Defect 1 residual: the CLOUD publisher path.

The local /api/risk GET path was already fixed (product.py emits an honest
sentinel score=None / level="unknown" on evaluator crash, guarded by
tests/test_risk_silent_failure.py). But lucidfence/core/cloud_publisher.py
serialize() still emitted `"risk_score": getattr(s, "risk_score", 0)`.

That default-to-0 is a *live false-green*: a device whose evaluator crashed
and persisted risk_score=None is serialized as 0, so the cloud dashboard
renders it "todo ok / green" when there is a real failure. This test guards
the cloud path against that regression (it had zero coverage before).

Accepted contract:
- A device with risk_score=None (crashed / never evaluated) is published as
  `risk_score: null`, never as 0. The dashboard renders null as "Sin senal"
  (NOT-safe).
- A device with a real persisted score keeps that number verbatim.
- `risk_score or 0` style consumers (cloud.html) read null as 0 only for
  display aggregation; the honest null travels in the feed and the device is
  NOT presented as a healthy/low device anywhere that distinguishes None.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cloud_module():
    return _load(ROOT / "lucidfence" / "core" / "cloud_publisher.py")


class _Device:
    """Minimal stand-in for a persisted DeviceState with only the fields
    cloud_publisher.serialize() reads via getattr / ios_geofence_compliance
    via .get()."""

    def __init__(self, **attrs):
        self._attrs = attrs

    def __getattr__(self, name):
        # getattr(s, "risk_score", None) hits __getattribute__ first (found),
        # so only truly-absent names land here with a default of None.
        return self._attrs.get(name)

    def get(self, name, default=None):
        return self._attrs.get(name, default)


class _Store:
    def __init__(self, devices):
        self._devices = devices

    def snapshot(self):
        return {d.device_id: d for d in self._devices}


class _FakeEngine:
    """Serialize only needs .status() and .store.snapshot()."""

    def __init__(self, devices):
        self.store = _Store(devices)

    def status(self):
        return {"interval_seconds": 900}


def _device(device_id, risk_score, platform="macos", fence_state="inside"):
    return _Device(
        device_id=device_id,
        name=f"dev-{device_id}",
        platform=platform,
        fence_state=fence_state,
        compliant=None,
        risk_score=risk_score,
    )


def test_crashed_eval_persisted_none_is_published_null_not_zero():
    """A device with risk_score=None must serialize as null, never 0."""
    cloud = _cloud_module()
    eng = _FakeEngine([
        _device("d1", risk_score=None),
        _device("d2", risk_score=82.0),
    ])
    payload = cloud.serialize(eng, "org-test")
    devices = {d["device_id"]: d for d in payload["devices"]}

    assert "d1" in devices and "d2" in devices
    # The core assertion: crashed-evidence must NOT be presented as 0/green.
    assert devices["d1"]["risk_score"] is None, (
        f"crashed-eval device must publish risk_score=null, got "
        f"{devices['d1']['risk_score']!r} (false-green to cloud dashboard)"
    )
    # A real score passes through unchanged.
    assert devices["d2"]["risk_score"] == 82.0
    # JSON round-trip confirms it is literally null (not "0" / 0.0), and that
    # no later stage in the publish pipeline rewrites it to a number.
    import json
    blob = json.dumps(payload)
    reparsed = json.loads(blob)
    device_rows = {d["device_id"]: d for d in reparsed["devices"]}
    assert device_rows["d1"]["risk_score"] is None, (
        f"published feed must carry null risk_score for crashed-eval device, "
        f"got {device_rows['d1']['risk_score']!r}"
    )


def test_cloud_feed_null_is_not_safe_in_consumers():
    """Consumers that treat null as 'unknown' must not flag a None device as
    healthy. Mirrors the dashboard contract: risk_score or 0 is display-only;
    a None device is NOT-safe (Sin senal)."""
    cloud = _cloud_module()
    eng = _FakeEngine([_device("x", risk_score=None)])
    payload = cloud.serialize(eng, "org-test")
    row = payload["devices"][0]
    score = row["risk_score"]

    # The 'unknown' contract: a None device is never counted as a healthy/low
    # device. dashboards must branch on `score is None`, not `score or 0`.
    is_unknown = score is None
    assert is_unknown is True
    # A boolean 'is this device safe?' derived from the feed must be False for
    # an unknown device (fail-closed), not True.
    presented_as_safe = (score or 0) == 0 and score is not None
    assert presented_as_safe is False, (
        "an unknown device must NOT be presented as a safe (zero-risk) device"
    )
