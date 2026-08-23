"""Enums and dataclasses for the device-attestation verifier."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AttestationState(str, Enum):
    """Verification verdict. ``str`` mixin so it serializes cleanly to JSON.

    Red line #110: the ONLY state the product may render as \"Verified\" is
    ``VERIFIED``. Every other state maps to an un-trusted label
    (``UNVERIFIED`` / ``UNKNOWN`` / ``REJECTED``) and MUST never be shown as
    trusted.
    """

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"
    REJECTED = "rejected"

    @property
    def is_trusted(self) -> bool:
        """True only for VERIFIED. Drives the #110 render gate."""
        return self is AttestationState.VERIFIED


class Provider(str, Enum):
    APPLE = "apple"
    ANDROID = "android"
    WINDOWS = "windows"


@dataclass
class DeviceAttestation:
    """Parsed + verified attestation result.

    ``provider``: which vendor produced the blob.
    ``raw_blob``: original bytes as received (kept for audit / replay evidence).
    ``parsed_claims``: dict of vendor-specific claims extracted from the blob.
    ``verification_result``: AttestationState verdict.
    ``evidence_refs``: list of human-readable evidence strings (chain, nonce,
        signature checks) so the verdict is explainable (T3MP3ST honesty spine).
    """

    provider: Provider
    raw_blob: bytes
    parsed_claims: dict[str, Any] = field(default_factory=dict)
    verification_result: AttestationState = AttestationState.UNKNOWN
    evidence_refs: list[str] = field(default_factory=list)
    # Optional reconciliation of the device identity across UEM sources.
    device_id: str | None = None
    error: str | None = None

    def to_evidence(self) -> dict[str, Any]:
        """Export as a Risk Engine evidence signal (pattern: location_integrity)."""
        return {
            "method": "device-attestation",
            "prediction": False,
            "provider": self.provider.value,
            "result": self.verification_result.value,
            "trusted": self.verification_result.is_trusted,
            "device_id": self.device_id,
            "evidence_refs": list(self.evidence_refs),
            "error": self.error,
        }


@dataclass
class Reconciliation:
    """Cross-UEM identity correlation record.

    IMPORTANT (red line C4, dictamen §3): ``auto_fused`` is ALWAYS ``False``.
    LucidFence correlates candidate identities and exposes the linkage with a
    confidence score, but NEVER merges two UEM records into one canonical
    identity on its own. A human/tenant confirms any merge.
    """

    method: str
    confidence: float
    linked_ids: list[str] = field(default_factory=list)
    candidate_ids: list[str] = field(default_factory=list)
    auto_fused: bool = False

    def to_evidence(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "confidence": round(self.confidence, 4),
            "linked_ids": list(self.linked_ids),
            "candidate_ids": list(self.candidate_ids),
            "auto_fused": self.auto_fused,  # always False by construction
        }
