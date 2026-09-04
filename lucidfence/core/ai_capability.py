"""Read-only inventory of LOCAL AI capability on managed endpoints.

Issue #252 — "Inventario local de capacidades de IA en endpoints".

Design contract (from the issue):
  * Read-only model. We ingest ONLY documented signals or explicit fixtures
    from adapters. We never inspect prompts, responses, or any PII.
  * Distinguish four independent facts about a single capability:
      - capability:   what the platform CAN do (declared)
      - enabled:      is the feature currently switched on (observed signal)
      - allowed_by_policy: does the MDM/UEM policy permit it
      - observed_use: has the platform actually exercised it (signal only)
  * Every field is unknown-safe: absence of signal => "unknown", never a
    guessed-false or a carried-over previous value.
  * Each ingested signal keeps its `source` (which adapter / fixture) and
    `method` (how it was obtained), so an auditor can trace every claim.
  * The summary reports COVERAGE (signals present vs absent per platform),
    never a single fleet-wide percentage that hides blind spots.

This module is intentionally free of any network, AI runtime, or paid
dependency. It is pure deterministic Python so it is testable offline.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from typing import Optional
from enum import Enum

# Sentinel for "we have no signal either way" — MUST be distinct from False.
UNKNOWN = "unknown"


class SignalFreshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass
class AICapabilityRecord:
    """One capability observation for one device/platform.

    `capability`, `enabled`, `allowed_by_policy`, `observed_use` are each
    independently unknown-safe. We never backfill a missing field from a
    previous record — that is the anti-pattern the issue forbids.
    """

    device_id: str
    platform: str
    capability: str  # e.g. "apple_intelligence", "on_device_speech", "npu_inference"
    source: str  # adapter or fixture that produced this record
    method: str  # how it was obtained, e.g. "mdm_restrictions_profile"
    capability_declared: Optional[bool] = None  # can the platform do it?
    enabled: Optional[bool] = None  # is it switched on right now?
    allowed_by_policy: Optional[bool] = None  # does policy permit it?
    observed_use: Optional[bool] = None  # has it actually been exercised?
    observed_at: Optional[float] = None  # epoch seconds of the signal
    stale_after_seconds: Optional[int] = None  # policy-defined freshness window

    def freshness(self) -> SignalFreshness:
        if self.observed_at is None or self.stale_after_seconds is None:
            return SignalFreshness.UNKNOWN
        age = time.time() - self.observed_at
        if age > self.stale_after_seconds:
            return SignalFreshness.STALE
        return SignalFreshness.FRESH

    def as_dict(self) -> dict:
        d = asdict(self)
        d["freshness"] = self.freshness().value
        return d


def _norm(v) -> Optional[bool]:
    """Normalize a raw signal to None/True/False; anything unknown stays None."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "1", "yes", "on", "allowed", "enabled"):
            return True
        if s in ("false", "0", "no", "off", "denied", "disabled"):
            return False
    return None  # unknown strings are NOT coerced to False


def ingest(signals: list[dict]) -> list[AICapabilityRecord]:
    """Turn raw adapter/fixture signals into typed, unknown-safe records.

    Each signal dict may carry: device_id, platform, capability, source,
    method, capability_declared, enabled, allowed_by_policy, observed_use,
    observed_at, stale_after_seconds. Missing boolean keys become None
    (UNKNOWN) rather than False.
    """
    out: list[AICapabilityRecord] = []
    for s in signals:
        rec = AICapabilityRecord(
            device_id=s.get("device_id", "unknown"),
            platform=(s.get("platform") or "unknown"),
            capability=s.get("capability", "unknown"),
            source=s.get("source", "unspecified"),
            method=s.get("method", "unspecified"),
            capability_declared=_norm(s.get("capability_declared")),
            enabled=_norm(s.get("enabled")),
            allowed_by_policy=_norm(s.get("allowed_by_policy")),
            observed_use=_norm(s.get("observed_use")),
            observed_at=s.get("observed_at"),
            stale_after_seconds=s.get("stale_after_seconds"),
        )
        out.append(rec)
    return out


def coverage(records: list[AICapabilityRecord]) -> dict:
    """Coverage = signals present vs absent, per platform and per capability.

    We deliberately report COVERAGE (how many endpoints have a real signal for
    a given capability) rather than a single fleet-wide percentage, because a
    percentage over the whole fleet would mask platforms with zero signal.
    """
    platforms: dict[str, dict] = {}
    for r in records:
        p = platforms.setdefault(
            r.platform,
            {"platform": r.platform, "devices": set(), "by_capability": {}},
        )
        p["devices"].add(r.device_id)
        cap = p["by_capability"].setdefault(
            r.capability,
            {
                "capability": r.capability,
                "with_signal": 0,
                "unknown": 0,
                "declared": 0,
                "enabled": 0,
                "allowed_by_policy": 0,
                "observed_use": 0,
            },
        )
        if None in (
            r.capability_declared,
            r.enabled,
            r.allowed_by_policy,
            r.observed_use,
        ):
            cap["unknown"] += 1
        else:
            cap["with_signal"] += 1
        if r.capability_declared is True:
            cap["declared"] += 1
        if r.enabled is True:
            cap["enabled"] += 1
        if r.allowed_by_policy is True:
            cap["allowed_by_policy"] += 1
        if r.observed_use is True:
            cap["observed_use"] += 1

    result = []
    for p in platforms.values():
        total = len(p["devices"])
        caps = []
        for c in p["by_capability"].values():
            cov = round(100 * c["with_signal"] / total) if total else 0
            # Coverage is per-capability-per-platform, honest about blind spots.
            caps.append(
                {
                    "capability": c["capability"],
                    "coverage_percent": cov,
                    "devices_with_signal": c["with_signal"],
                    "devices_unknown": c["unknown"],
                    "declared": c["declared"],
                    "enabled": c["enabled"],
                    "allowed_by_policy": c["allowed_by_policy"],
                    "observed_use": c["observed_use"],
                }
            )
        result.append(
            {
                "platform": p["platform"],
                "device_count": total,
                "capabilities": caps,
            }
        )
    return {"platforms": result, "total_records": len(records)}


# ---------------------------------------------------------------------------
# Fixtures (explicit, documented-signal only — no live inspection of models)
# ---------------------------------------------------------------------------

FIXTURES: dict[str, list[dict]] = {
    # Apple Intelligence explicitly ALLOWED by a restriction profile, fresh signal.
    "apple_intelligence_allowed_fresh": [
        {
            "device_id": "dev-a1",
            "platform": "ios",
            "capability": "apple_intelligence",
            "source": "fixture",
            "method": "mdm_restrictions_profile",
            "capability_declared": True,
            "enabled": True,
            "allowed_by_policy": True,
            "observed_use": False,
            "observed_at": time.time(),
            "stale_after_seconds": 86400,
        }
    ],
    # Apple Intelligence explicitly RESTRICTED by policy (capability exists,
    # but policy denies it). Fresh signal.
    "apple_intelligence_restricted_fresh": [
        {
            "device_id": "dev-b1",
            "platform": "macos",
            "capability": "apple_intelligence",
            "source": "fixture",
            "method": "mdm_restrictions_profile",
            "capability_declared": True,
            "enabled": False,
            "allowed_by_policy": False,
            "observed_use": False,
            "observed_at": time.time(),
            "stale_after_seconds": 86400,
        }
    ],
    # Platform with NO signal at all — must surface as UNKNOWN, not False.
    "platform_no_signal": [
        {
            "device_id": "dev-c1",
            "platform": "android",
            "capability": "on_device_ai",
            "source": "fixture",
            "method": "none",
            # all booleans omitted -> unknown-safe
        }
    ],
    # Stale data: a signal exists but is older than the freshness window.
    "stale_data": [
        {
            "device_id": "dev-d1",
            "platform": "ios",
            "capability": "apple_intelligence",
            "source": "fixture",
            "method": "mdm_restrictions_profile",
            "capability_declared": True,
            "enabled": True,
            "allowed_by_policy": True,
            "observed_use": True,
            # 30 days old, window is 1 day -> STALE
            "observed_at": time.time() - (30 * 86400),
            "stale_after_seconds": 86400,
        }
    ],
}


def load_fixture(name: str) -> list[AICapabilityRecord]:
    if name not in FIXTURES:
        raise KeyError(f"unknown ai-capability fixture: {name}")
    return ingest(FIXTURES[name])
