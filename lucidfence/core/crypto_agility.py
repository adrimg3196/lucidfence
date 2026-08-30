"""Read-only inventory of cryptographic agility and post-quantum readiness.

Issue #248 — "Inventario de cripto-agilidad y preparación poscuántica".

Design contract (from the issue):
  * Read-only model. We ingest ONLY declared certificates, protocol/suite
    strings, or declared dependencies from documented signals or explicit
    fixtures. We never scan networks or touch live secret material.
  * Classify each observable into one of: quantum_vulnerable, pqc_ready,
    hybrid, unknown, not_applicable — using VERSIONED rules so the logic is
    auditable and can evolve without silent behaviour change.
  * Distinguish REAL discovery (a signal we actually observed) from INFERENCE
    (a classification we derived from a weaker signal), and report freshness
    for every signal.
  * Absence of an inventory MUST NOT inflate a readiness score: an endpoint
    with no signal contributes "unknown", which lowers coverage rather than
    pretending readiness.
  * The result carries a PROPOSED remediation/research plan that is never
    executed by this module — no certificate is replaced, no algorithm changed.
  * No private key, secret, or opaque material is ever persisted: the model
    carries only public metadata (algorithms, key sizes, protocols, versions).

This module is intentionally free of any network, crypto runtime that touches
secret material, or paid dependency. It is pure deterministic Python so it is
testable offline.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

# Sentinel for "we have no signal either way" — MUST be distinct from a guessed
# readiness value. Absence of evidence is NOT evidence of readiness.
UNKNOWN = "unknown"


class SignalFreshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class CryptoClass(str, Enum):
    """Versioned classification taxonomy for a single crypto observable."""

    QUANTUM_VULNERABLE = "quantum_vulnerable"
    PQC_READY = "pqc_ready"
    HYBRID = "hybrid"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


# The rule-set version. Every classification records which version produced it,
# so an auditor can tell whether a result came from a stale rule set.
RULES_VERSION = "2026-08-24"


# Known PQC algorithm families (NIST FIPS 203/204/205) and their RFC names.
_PQC_KEMS = {"ml-kem", "kyber"}
_PQC_SIGNS = {"ml-dsa", "dilithium", "slh-dsa", "sphincs+"}
# Classical algorithms whose security is eroded by a cryptographically relevant
# quantum computer (Shor). Presence WITHOUT a PQC counterpart => vulnerable.
_CLASSICAL_QV = {
    "rsa", "ecdsa", "ecdh", "ecc", "ec", "dh", "dsa", "ed25519", "ed448",
    "x25519", "x448", "classical",
}


@dataclass
class CryptoEvidence:
    """One observed crypto artifact on one device/platform.

    `algorithm`, `key_size`, `protocol`, `cert_signal` are each independently
    unknown-safe. We never backfill a missing field from a previous record.
    """

    device_id: str
    platform: str
    source: str  # adapter or fixture that produced this record
    method: str  # how it was obtained, e.g. "certificate_metadata"
    artifact: str  # human label, e.g. "tls_cert", "ssh_host_key", "dependency"
    algorithm: Optional[str] = None  # e.g. "rsa", "ml-kem", "ecdsa"
    key_size: Optional[int] = None
    protocol: Optional[str] = None  # e.g. "TLS1.3"
    cert_signal: Optional[bool] = None  # did we see a certificate at all?
    observed_at: Optional[float] = None
    stale_after_seconds: Optional[int] = None
    # Discovery provenance: did we SEE this, or INFER it from a weaker signal?
    discovery: str = "inferred"  # "observed" | "inferred"

    def freshness(self) -> SignalFreshness:
        if self.observed_at is None or self.stale_after_seconds is None:
            return SignalFreshness.UNKNOWN
        age = time.time() - self.observed_at
        if age > self.stale_after_seconds:
            return SignalFreshness.STALE
        return SignalFreshness.FRESH

    def has_private_material(self) -> bool:
        # Guard: this model must never carry secret material.
        forbidden = {"private_key", "secret", "token", "password", "key_material"}
        return any(t in (self.algorithm or "").lower() for t in forbidden) or any(
            t in (self.source or "").lower() for t in forbidden
        )

    def as_dict(self) -> dict:
        d = asdict(self)
        d["freshness"] = self.freshness().value
        return d


def _norm_alg(algorithm: Optional[str]) -> Optional[str]:
    """Normalize a raw algorithm string to a comparable family token."""
    if algorithm is None:
        return None
    s = algorithm.strip().lower()
    if not s:
        return None
    return s


def classify(ev: CryptoEvidence) -> tuple[CryptoClass, str]:
    """Return (classification, rule_id) using the versioned rule set.

    The rule_id cites which NIST-oriented rule produced the decision so the
    result is auditable. A missing algorithm is NEVER classified as ready.
    """
    alg = _norm_alg(ev.algorithm)
    if alg is None:
        # No signal about the algorithm => unknown, never quantum_vulnerable
        # by assumption and NEVER pqc_ready. This is the "absence does not
        # improve readiness" guard.
        return CryptoClass.UNKNOWN, f"rule:no-signal:{RULES_VERSION}"

    is_pqc = alg in _PQC_KEMS or alg in _PQC_SIGNS
    is_classical_qv = alg in _CLASSICAL_QV

    if is_pqc:
        return CryptoClass.PQC_READY, f"rule:pqc-family:{RULES_VERSION}"
    if is_classical_qv:
        # Classical algorithm with no PQC counterpart observed on this artifact.
        return (
            CryptoClass.QUANTUM_VULNERABLE,
            f"rule:classical-qv:{RULES_VERSION}",
        )
    # A non-PQC, non-classical-QV algorithm (e.g. "aes256" symmetric, which is
    # not in the QV set for Grover-only; or an unrecognized string). Symmetric
    # AES is not broken by Shor; treat recognized symmetric as not_applicable to
    # the QV migration, unrecognized as unknown.
    if alg in {"aes", "aes256", "aes128", "chacha20", "sha256", "sha3", "sha384"}:
        return (
            CryptoClass.NOT_APPLICABLE,
            f"rule:symmetric-not-qv:{RULES_VERSION}",
        )
    return CryptoClass.UNKNOWN, f"rule:unrecognized:{RULES_VERSION}"


def device_posture(records: list[CryptoEvidence]) -> dict:
    """Aggregate per-artifact classifications into a per-DEVICE posture.

    A device is HYBRID when it simultaneously carries a classical-QV artifact
    AND a PQC-ready artifact (it has a quantum-resistant path alongside the
    classical one). This is the device-level class the issue asks for, derived
    from the versioned per-artifact rules above.
    """
    by_device: dict[str, list[CryptoClass]] = {}
    ev_by_device: dict[str, list[CryptoEvidence]] = {}
    for r in records:
        cls, _ = classify(r)
        by_device.setdefault(r.device_id, []).append(cls)
        ev_by_device.setdefault(r.device_id, []).append(r)

    result = {}
    for dev, classes in by_device.items():
        has_pqc = CryptoClass.PQC_READY in classes
        has_qv = CryptoClass.QUANTUM_VULNERABLE in classes
        has_na = CryptoClass.NOT_APPLICABLE in classes
        has_unknown = CryptoClass.UNKNOWN in classes

        if has_pqc and has_qv:
            posture = CryptoClass.HYBRID
        elif has_pqc:
            posture = CryptoClass.PQC_READY
        elif has_qv:
            posture = CryptoClass.QUANTUM_VULNERABLE
        elif has_na and not (has_unknown):
            posture = CryptoClass.NOT_APPLICABLE
        else:
            posture = CryptoClass.UNKNOWN

        evs = ev_by_device[dev]
        result[dev] = {
            "device_id": dev,
            "platform": evs[0].platform,
            "posture": posture.value,
            "rules_version": RULES_VERSION,
            "artifacts": [e.as_dict() for e in evs],
            "classification_note": (
                "hybrid = classical-QV + PQC-ready present on same device"
                if posture is CryptoClass.HYBRID
                else ""
            ),
        }
    return result


def ingest(signals: list[dict]) -> list[CryptoEvidence]:
    """Turn raw adapter/fixture signals into typed, unknown-safe evidence.

    Missing algorithm/key_size/protocol/cert_signal become None (UNKNOWN)
    rather than a guessed value. `discovery` defaults to "inferred" unless the
    raw signal explicitly says "observed".
    """
    out: list[CryptoEvidence] = []
    for s in signals:
        disc = s.get("discovery", "inferred")
        if disc not in ("observed", "inferred"):
            disc = "inferred"
        ev = CryptoEvidence(
            device_id=s.get("device_id", "unknown"),
            platform=(s.get("platform") or "unknown"),
            source=s.get("source", "unspecified"),
            method=s.get("method", "unspecified"),
            artifact=s.get("artifact", "unspecified"),
            algorithm=_norm_alg(s.get("algorithm")),
            key_size=s.get("key_size"),
            protocol=s.get("protocol"),
            cert_signal=s.get("cert_signal"),
            observed_at=s.get("observed_at"),
            stale_after_seconds=s.get("stale_after_seconds"),
            discovery=disc,
        )
        if ev.has_private_material():
            # Fail-closed: refuse to persist anything that looks like secret
            # material. Drop it rather than carry it.
            continue
        out.append(ev)
    return out


def readiness_score(records: list[CryptoEvidence]) -> dict:
    """Honest readiness: coverage of PQC-ready / hybrid vs the whole fleet.

    Endpoints with NO signal count as "unknown", which REDUCES coverage rather
    than inflating the score. A fleet with zero evidence therefore reports
    readiness 0 and coverage 0 — never a misleading high number.
    """
    total = len(records)
    classified = {
        CryptoClass.QUANTUM_VULNERABLE: 0,
        CryptoClass.PQC_READY: 0,
        CryptoClass.HYBRID: 0,
        CryptoClass.NOT_APPLICABLE: 0,
        CryptoClass.UNKNOWN: 0,
    }
    for r in records:
        cls, _ = classify(r)
        classified[cls] += 1

    # Readiness numerator = only PQC_READY + HYBRID artifacts (real readiness).
    ready = classified[CryptoClass.PQC_READY] + classified[CryptoClass.HYBRID]
    # Denominator = artifacts we could classify (exclude not_applicable, which
    # is out of scope for the QV migration, and unknown, which is a blind spot).
    in_scope = (
        classified[CryptoClass.PQC_READY]
        + classified[CryptoClass.HYBRID]
        + classified[CryptoClass.QUANTUM_VULNERABLE]
    )
    readiness_percent = round(100 * ready / in_scope) if in_scope else 0
    # Coverage = how many artifacts we actually have signal for (not unknown).
    with_signal = total - classified[CryptoClass.UNKNOWN]
    coverage_percent = round(100 * with_signal / total) if total else 0

    return {
        "rules_version": RULES_VERSION,
        "total_artifacts": total,
        "classified": {k.value: v for k, v in classified.items()},
        "ready_artifacts": ready,
        "in_scope_artifacts": in_scope,
        "readiness_percent": readiness_percent,
        "coverage_percent": coverage_percent,
        "note": (
            "readiness_percent reflects ONLY PQC_READY/HYBRID over in-scope "
            "artifacts; 'unknown' artifacts lower coverage and are NOT counted "
            "as ready."
        ),
    }


def proposed_remediation(records: list[CryptoEvidence]) -> list[dict]:
    """Propose a research/remediation plan. NEVER executes anything.

    Returns one plan item per quantum_vulnerable artifact, citing the rule and
    the observed evidence. This is advisory output for an administrator.
    """
    plan: list[dict] = []
    for r in records:
        cls, rule_id = classify(r)
        if cls is CryptoClass.QUANTUM_VULNERABLE:
            plan.append(
                {
                    "device_id": r.device_id,
                    "platform": r.platform,
                    "artifact": r.artifact,
                    "algorithm": r.algorithm,
                    "key_size": r.key_size,
                    "protocol": r.protocol,
                    "classification": cls.value,
                    "rule_id": rule_id,
                    "evidence": r.as_dict(),
                    "action": "PROPOSED: plan migration to a hybrid (classical+PQC) "
                    "or PQC-only scheme; verify against NIST FIPS 203/204/205. "
                    "NOT executed by this module.",
                    "executed": False,
                }
            )
    return plan


# ---------------------------------------------------------------------------
# Fixtures (explicit, documented-signal only — no live secret inspection)
# ---------------------------------------------------------------------------

FIXTURES: dict[str, list[dict]] = {
    # Classical RSA cert observed, fresh signal -> quantum_vulnerable.
    "rsa_cert_fresh": [
        {
            "device_id": "dev-a1",
            "platform": "ios",
            "source": "fixture",
            "method": "certificate_metadata",
            "artifact": "tls_server_cert",
            "algorithm": "RSA",
            "key_size": 2048,
            "protocol": "TLS1.3",
            "cert_signal": True,
            "observed_at": time.time(),
            "stale_after_seconds": 86400,
            "discovery": "observed",
        }
    ],
    # ECC classic key -> quantum_vulnerable.
    "ecc_key_fresh": [
        {
            "device_id": "dev-b1",
            "platform": "macos",
            "source": "fixture",
            "method": "certificate_metadata",
            "artifact": "ssh_host_key",
            "algorithm": "ECDSA",
            "key_size": 256,
            "cert_signal": True,
            "observed_at": time.time(),
            "stale_after_seconds": 86400,
            "discovery": "observed",
        }
    ],
    # ML-KEM (FIPS 203) observed -> pqc_ready.
    "mlkem_fresh": [
        {
            "device_id": "dev-c1",
            "platform": "linux",
            "source": "fixture",
            "method": "dependency_manifest",
            "artifact": "tls_kem",
            "algorithm": "ML-KEM",
            "key_size": 768,
            "protocol": "TLS1.3",
            "cert_signal": False,
            "observed_at": time.time(),
            "stale_after_seconds": 86400,
            "discovery": "observed",
        }
    ],
    # Hybrid: RSA + ML-KEM declared together -> hybrid (classical present, PQC
    # present). We model hybrid as an artifact whose algorithm lists PQC and a
    # classical counterpart is also observed on the same device elsewhere; here
    # we represent it directly via a fixture flag-less inference rule: an
    # artifact whose algorithm is a recognized classical AND the same device has
    # a PQC artifact counts as HYBRID at aggregation time. For the unit fixture
    # we mark a device that has both.
    "hybrid_device": [
        {
            "device_id": "dev-d1",
            "platform": "linux",
            "source": "fixture",
            "method": "dependency_manifest",
            "artifact": "tls_cert",
            "algorithm": "RSA",
            "key_size": 4096,
            "protocol": "TLS1.3",
            "cert_signal": True,
            "observed_at": time.time(),
            "stale_after_seconds": 86400,
            "discovery": "observed",
        },
        {
            "device_id": "dev-d1",
            "platform": "linux",
            "source": "fixture",
            "method": "dependency_manifest",
            "artifact": "tls_kem",
            "algorithm": "ML-KEM",
            "key_size": 768,
            "cert_signal": False,
            "observed_at": time.time(),
            "stale_after_seconds": 86400,
            "discovery": "observed",
        },
    ],
    # Artifact with NO algorithm signal at all -> unknown (must NOT be ready).
    "no_signal_unknown": [
        {
            "device_id": "dev-e1",
            "platform": "android",
            "source": "fixture",
            "method": "none",
            "artifact": "vpn_cert",
            # algorithm omitted -> unknown-safe
            "cert_signal": None,
        }
    ],
    # ML-DSA (FIPS 204) observed -> pqc_ready (signature PQC).
    "mldsa_fresh": [
        {
            "device_id": "dev-g1",
            "platform": "windows",
            "source": "fixture",
            "method": "dependency_manifest",
            "artifact": "code_sign_cert",
            "algorithm": "ML-DSA",
            "key_size": 65,
            "cert_signal": True,
            "observed_at": time.time(),
            "stale_after_seconds": 86400,
            "discovery": "observed",
        }
    ],
    # Stale classical signal: older than freshness window -> still classified
    # but flagged STALE so the admin knows to re-collect.
    "stale_rsa": [
        {
            "device_id": "dev-f1",
            "platform": "ios",
            "source": "fixture",
            "method": "certificate_metadata",
            "artifact": "tls_server_cert",
            "algorithm": "RSA",
            "key_size": 2048,
            "protocol": "TLS1.2",
            "cert_signal": True,
            # 30 days old, window 1 day -> STALE
            "observed_at": time.time() - (30 * 86400),
            "stale_after_seconds": 86400,
            "discovery": "observed",
        }
    ],
}


def load_fixture(name: str) -> list[CryptoEvidence]:
    if name not in FIXTURES:
        raise KeyError(f"unknown crypto-agility fixture: {name}")
    return ingest(FIXTURES[name])
