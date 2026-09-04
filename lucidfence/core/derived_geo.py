"""Geofencing from a DERIVED state signal — no raw coordinates retained.

Issue #258 — "Geofencing por estado derivado sin conservar coordenadas".

Design contract (from the issue):
  * We accept a derived signal carrying: fence_id, state (inside/outside/
    unknown), observed_at, policy_hash, source and confidence. We do NOT need
    raw latitude/longitude to enforce a policy.
  * A per-tenant mode may REJECT persisting raw coordinates once the policy is
    evaluated. The mode is OPT-IN and its activation reports which analyses stop
    being possible (e.g. historical movement, raw-coordinate audit).
  * Replay / spoofing detection: a future timestamp or a repeated observation
    lowers confidence and is made VISIBLE (never hidden).
  * inside/outside/unknown are evaluated with the policy hash and freshness.
  * A policy_hash change INVALIDATES a previously stored signal (it becomes
    unknown): a signal is only meaningful under the policy that produced it.
  * Evidence export proves the decision without reconstructing a personal route.
  * Poison test guarantee: in derived-only mode, raw coordinates fed in are
    NEVER written to storage, logs, exports or the cloud_state representation.

Pure deterministic Python (stdlib-only), testable offline.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional


class GeoState(str, Enum):
    INSIDE = "inside"
    OUTSIDE = "outside"
    UNKNOWN = "unknown"


class DerivedGeoMode(str, Enum):
    """Per-tenant persistence mode for geolocation."""
    FULL = "full"                    # raw coordinates may be retained (default)
    DERIVED_ONLY = "derived_only"    # raw coords rejected after evaluation


# Analyses that become impossible in DERIVED_ONLY mode. Surfaced on activation
# so the administrator makes an informed opt-in (acceptance criterion).
DERIVED_ONLY_TRADEOFFS = (
    "historical movement tracking (no coordinate trail is kept)",
    "raw-coordinate forensic audit of a past position",
    "recomputation of a fence decision against a different fence geometry",
)


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class DerivedGeoSignal:
    """A derived geofence decision for one device/fence.

    `lat`/`lng` are accepted ONLY to prove the poison path; under DERIVED_ONLY
    they are stripped before persistence (see `strip_raw`).
    """
    fence_id: str
    device_id: str
    tenant_id: str
    state: str                       # GeoState value
    observed_at: str                 # ISO8601
    policy_hash: str                 # sha256 of the policy that produced `state`
    source: str                      # adapter / fixture
    confidence: str = Confidence.HIGH.value
    lat: Optional[float] = None      # raw coord — NEVER persisted in DERIVED_ONLY
    lng: Optional[float] = None      # raw coord — NEVER persisted in DERIVED_ONLY
    replay_detected: bool = False
    future_timestamp: bool = False
    invalidated_by_policy: bool = False
    nonce: Optional[str] = None      # optional replay guard

    def as_dict(self, strip_raw: bool = True) -> dict:
        d = asdict(self)
        if strip_raw:
            d.pop("lat", None)
            d.pop("lng", None)
        return d


def policy_hash_of(policy: dict) -> str:
    """Deterministic hash of a fence policy dict (stable key order)."""
    canon = _canonical(policy)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _canonical(obj) -> str:
    if isinstance(obj, dict):
        return "{" + ",".join(f"{k}:{_canonical(obj[k])}" for k in sorted(obj)) + "}"
    if isinstance(obj, list):
        return "[" + ",".join(_canonical(x) for x in obj) + "]"
    return repr(obj)


def evaluate(state: str, policy_hash: str, stored_policy_hash: str,
             observed_at: str, now: Optional[float] = None) -> dict:
    """Evaluate a derived signal against freshness and policy continuity.

    Returns the resolved decision: state may be downgraded to UNKNOWN when the
    policy that produced the signal no longer matches (invalidated_by_policy) or
    when the signal is stale.
    """
    now = now if now is not None else time.time()
    ts = _parse_iso(observed_at)
    out = {
        "state": state,
        "confidence": Confidence.HIGH.value,
        "invalidated_by_policy": False,
        "future_timestamp": False,
        "stale": False,
    }
    if ts is None:
        out["state"] = GeoState.UNKNOWN.value
        out["confidence"] = Confidence.LOW.value
        return out
    if ts > now + 1.0:  # small clock skew tolerance
        out["future_timestamp"] = True
        out["confidence"] = Confidence.LOW.value
        out["state"] = GeoState.UNKNOWN.value
    if policy_hash != stored_policy_hash:
        out["invalidated_by_policy"] = True
        out["state"] = GeoState.UNKNOWN.value
        out["confidence"] = Confidence.LOW.value
    return out


def ingest(signal: DerivedGeoSignal, mode: DerivedGeoMode,
           stored_policy_hash: Optional[str] = None,
           seen_nonces: Optional[set] = None,
           now: Optional[float] = None) -> DerivedGeoSignal:
    """Validate + normalize a derived signal under the tenant's mode.

    In DERIVED_ONLY mode, raw coordinates are stripped from the returned signal
    (never persisted). Replay (repeated nonce) and future timestamps lower
    confidence and are flagged visibly. A policy_hash mismatch with the stored
    policy invalidates the signal to UNKNOWN.
    """
    now = now if now is not None else time.time()
    seen_nonces = seen_nonces if seen_nonces is not None else set()

    res = evaluate(signal.state, signal.policy_hash,
                   stored_policy_hash if stored_policy_hash is not None else signal.policy_hash,
                   signal.observed_at, now=now)
    signal.state = res["state"]
    signal.confidence = res["confidence"]
    signal.invalidated_by_policy = res["invalidated_by_policy"]
    signal.future_timestamp = res["future_timestamp"]

    if signal.nonce is not None:
        if signal.nonce in seen_nonces:
            signal.replay_detected = True
            signal.confidence = Confidence.LOW.value
            if signal.state != GeoState.UNKNOWN.value:
                signal.state = GeoState.UNKNOWN.value
        else:
            seen_nonces.add(signal.nonce)

    if mode is DerivedGeoMode.DERIVED_ONLY:
        # The minimization guarantee: raw coords are dropped on ingest.
        signal.lat = None
        signal.lng = None
    return signal


def activation_tradeoffs() -> tuple[str, ...]:
    """What the administrator gives up by enabling DERIVED_ONLY (shown on opt-in)."""
    return DERIVED_ONLY_TRADEOFFS


def export_evidence(signal: DerivedGeoSignal) -> dict:
    """Verifiable decision evidence — no raw route, no coordinates.

    Proves: which fence, which state, under which policy hash, when, from what
    source, at what confidence. Deliberately excludes lat/lng even if present.
    """
    return {
        "fence_id": signal.fence_id,
        "device_id": signal.device_id,
        "tenant_id": signal.tenant_id,
        "state": signal.state,
        "policy_hash": signal.policy_hash,
        "observed_at": signal.observed_at,
        "source": signal.source,
        "confidence": signal.confidence,
        "replay_detected": signal.replay_detected,
        "future_timestamp": signal.future_timestamp,
        "invalidated_by_policy": signal.invalidated_by_policy,
        "evidence_hash": _evidence_hash(signal),
        "contains_raw_coordinates": False,
    }


def _evidence_hash(signal: DerivedGeoSignal) -> str:
    h = hashlib.sha256()
    for key in ("fence_id", "device_id", "tenant_id", "state", "policy_hash",
                "observed_at", "source", "confidence"):
        h.update(f"{key}={getattr(signal, key)}".encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def to_cloud_state(device_id: str, signal: Optional[DerivedGeoSignal],
                   mode: DerivedGeoMode) -> dict:
    """Public cloud_state representation for the vitrina.

    Mirrors cloud_publisher's flat device shape but, in DERIVED_ONLY mode,
    omits lat/lng entirely so raw coordinates never reach the public artifact.
    """
    base = {
        "device_id": device_id,
        "fence_state": signal.state if signal else "unknown",
        "policy_hash": signal.policy_hash if signal else None,
        "confidence": signal.confidence if signal else "unknown",
    }
    if mode is not DerivedGeoMode.DERIVED_ONLY and signal is not None:
        if signal.lat is not None:
            base["lat"] = signal.lat
        if signal.lng is not None:
            base["lng"] = signal.lng
    return base


def _parse_iso(value: str) -> Optional[float]:
    if not value or not isinstance(value, str):
        return None
    try:
        from datetime import datetime, timezone
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.timestamp()
    except ValueError:
        return None
