"""Sobre neutral de atestación de dispositivo.

Normaliza evidencias Apple Managed Device Attestation, Android Enterprise
Device Trust y Windows Device Health Attestation a un contrato local común. El
módulo NO verifica criptografía de fabricantes: conserva procedencia,
vigencia, hash del payload/veredicto y estado de firma reportado por el
verificador oficial. Lo desconocido viaja como ``unknown``/``None`` y nunca se
convierte en incumplimiento.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

MODEL_VERSION = "1.0"
CANONICAL_CLAIMS = ("hardware_backed", "managed", "os_integrity", "encryption")
SIGNATURE_STATUSES = {"verified", "unverified", "invalid", "unknown"}
VENDOR_SOURCES = {"apple", "android", "windows"}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AttestationError(ValueError):
    """Raised when a vendor attestation cannot be represented honestly."""


def _canonical_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _parse_ts(value: Any, field_name: str, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise AttestationError(f"{field_name} required")
        return None
    if not isinstance(value, str) or not value.strip():
        raise AttestationError(f"{field_name} must be an ISO-8601 string")
    text = value.strip()
    parseable = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        dt = datetime.fromisoformat(parseable)
    except ValueError as exc:
        raise AttestationError(f"{field_name} must be ISO-8601") from exc
    if dt.tzinfo is None:
        raise AttestationError(f"{field_name} must include timezone")
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _validate_time_order(issued_at: str | None, observed_at: str | None, expires_at: str | None) -> None:
    issued = _dt(issued_at)
    observed = _dt(observed_at)
    expires = _dt(expires_at)
    if issued and observed and issued > observed:
        raise AttestationError("issued_at after observed_at")
    if issued and expires and expires < issued:
        raise AttestationError("expires_at before issued_at")
    if observed and expires and expires < observed:
        raise AttestationError("expires_at before observed_at")


def _str_or_none(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AttestationError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_subject(value: Any) -> str:
    subject = _str_or_none(value, "subject")
    if subject is None:
        raise AttestationError("subject required")
    return subject


def _signature_status(value: Any) -> str:
    if value is None:
        return "unknown"
    if not isinstance(value, str):
        raise AttestationError("signature_status must be a string")
    status = value.strip().lower()
    if status not in SIGNATURE_STATUSES:
        raise AttestationError("signature_status invalid")
    return status


def _raw_hash(value: Any) -> str:
    if not isinstance(value, str):
        raise AttestationError("raw_hash must be sha256 hex")
    raw_hash = value.strip().lower()
    if not _SHA256_RE.fullmatch(raw_hash):
        raise AttestationError("raw_hash must be sha256 hex")
    return raw_hash


def _claim_value(source: str, raw_claims: dict, canonical: str, vendor_keys: tuple[str, ...]) -> dict:
    present = [key for key in vendor_keys if key in raw_claims]
    if not present:
        return {
            "status": "unknown",
            "value": None,
            "reason": f"claim absent in {source} attestation payload",
        }
    values: list[tuple[str, Any]] = []
    for key in present:
        value = raw_claims[key]
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            raise AttestationError(f"ambiguous boolean claim {key}")
        if canonical in {"hardware_backed", "managed", "os_integrity", "encryption"}:
            if not isinstance(value, bool):
                raise AttestationError(f"claim {key} must be boolean")
        values.append((key, value))
    expected = values[0][1]
    conflicts = [key for key, value in values[1:] if value != expected]
    if conflicts:
        names = ", ".join(present)
        raise AttestationError(f"conflicting aliases for {canonical}: {names}")
    key, value = values[0]
    return {
        "status": "asserted",
        "value": value,
        "reason": f"{source}:{key}",
    }


@dataclass(frozen=True)
class AttestationEnvelope:
    source: str
    subject: Any
    claims: dict
    issued_at: str | None
    observed_at: str
    expires_at: str | None
    nonce: str | None
    verifier: str | None
    signature_status: Any
    raw_hash: Any
    explanation: str
    provenance: dict = field(default_factory=dict)
    model_version: str = MODEL_VERSION

    def __post_init__(self) -> None:
        source = _str_or_none(self.source, "source")
        if source is None:
            raise AttestationError("source required")
        source = source.lower()
        if source not in VENDOR_SOURCES:
            raise AttestationError("source must be apple, android or windows")
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "subject", _require_subject(self.subject))
        if not isinstance(self.claims, dict):
            raise AttestationError("claims must be an object")
        for name in CANONICAL_CLAIMS:
            claim = self.claims.get(name)
            if not isinstance(claim, dict):
                raise AttestationError(f"claim {name} missing")
            status = claim.get("status")
            if status not in {"asserted", "unknown"}:
                raise AttestationError(f"claim {name} status invalid")
            if status == "unknown" and claim.get("value") is not None:
                raise AttestationError(f"claim {name} unknown must use null value")
            if status == "asserted" and not isinstance(claim.get("value"), bool):
                raise AttestationError(f"claim {name} asserted value must be boolean")
        issued_at = _parse_ts(self.issued_at, "issued_at")
        observed_at = _parse_ts(self.observed_at, "observed_at", required=True)
        expires_at = _parse_ts(self.expires_at, "expires_at")
        _validate_time_order(issued_at, observed_at, expires_at)
        object.__setattr__(self, "issued_at", issued_at)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "nonce", _str_or_none(self.nonce, "nonce"))
        object.__setattr__(self, "verifier", _str_or_none(self.verifier, "verifier"))
        object.__setattr__(self, "signature_status", _signature_status(self.signature_status))
        object.__setattr__(self, "raw_hash", _raw_hash(self.raw_hash))
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise AttestationError("explanation required")
        if not isinstance(self.provenance, dict):
            raise AttestationError("provenance must be an object")
        object.__setattr__(self, "model_version", str(self.model_version or MODEL_VERSION))

    def to_dict(self) -> dict:
        return {
            "claims": self.claims,
            "expires_at": self.expires_at,
            "explanation": self.explanation,
            "issued_at": self.issued_at,
            "model_version": self.model_version,
            "nonce": self.nonce,
            "observed_at": self.observed_at,
            "provenance": self.provenance,
            "raw_hash": self.raw_hash,
            "signature_status": self.signature_status,
            "source": self.source,
            "subject": self.subject,
            "verifier": self.verifier,
        }

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())


def envelope_from_dict(data: dict) -> AttestationEnvelope:
    if not isinstance(data, dict):
        raise AttestationError("attestation envelope must be an object")
    payload = dict(data)
    payload.setdefault("model_version", MODEL_VERSION)
    return AttestationEnvelope(**payload)


def envelope_from_json(text: str) -> AttestationEnvelope:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AttestationError("attestation JSON invalid") from exc
    return envelope_from_dict(data)


def _vendor_payload(source: str, raw: dict) -> tuple[str, dict, dict[str, tuple[str, ...]], str]:
    if source == "apple":
        payload = raw.get("managed_device_attestation") or {}
        return "managed_device_attestation", payload, {
            "hardware_backed": ("hardware_backed", "secure_enclave"),
            "managed": ("managed", "supervised"),
            "os_integrity": ("os_integrity",),
            "encryption": ("encryption", "filevault"),
        }, "certificate_chain_hash"
    if source == "android":
        payload = raw.get("device_trust") or {}
        return "device_trust", payload, {
            "hardware_backed": ("hardware_backed",),
            "managed": ("managed", "device_owner"),
            "os_integrity": ("os_integrity", "play_protect"),
            "encryption": ("encryption",),
        }, "verdict_hash"
    if source == "windows":
        payload = raw.get("health_attestation") or {}
        return "health_attestation", payload, {
            "hardware_backed": ("hardware_backed", "secure_boot"),
            "managed": ("managed",),
            "os_integrity": ("os_integrity", "code_integrity"),
            "encryption": ("encryption", "bitlocker"),
        }, "report_hash"
    raise AttestationError("source must be apple, android or windows")


def normalize_attestation(source: str, raw: dict, *, observed_at: str) -> AttestationEnvelope:
    if not isinstance(raw, dict):
        raise AttestationError("raw attestation must be an object")
    source = str(source or "").strip().lower()
    payload_name, payload, mappings, hash_key = _vendor_payload(source, raw)
    if not isinstance(payload, dict):
        raise AttestationError(f"{payload_name} must be an object")
    if "claims" in payload:
        raw_claims = payload["claims"]
    else:
        raw_claims = {}
    if not isinstance(raw_claims, dict):
        raise AttestationError("claims must be an object")
    claims = {
        canonical: _claim_value(source, raw_claims, canonical, keys)
        for canonical, keys in mappings.items()
    }
    issued_at = payload.get("issued_at", payload.get("evaluationTime"))
    expires_at = payload.get("expires_at", payload.get("expirationTime"))
    subject = raw.get("device_udid") or raw.get("device_id") or payload.get("subject")
    raw_hash = payload.get("raw_hash") or payload.get(hash_key)
    envelope = AttestationEnvelope(
        source=source,
        subject=subject,
        claims=claims,
        issued_at=issued_at,
        observed_at=observed_at,
        expires_at=expires_at,
        nonce=payload.get("nonce"),
        verifier=payload.get("verifier"),
        signature_status=payload.get("signature_status"),
        raw_hash=raw_hash,
        explanation=(
            f"{source} attestation for {subject}: signature {payload.get('signature_status') or 'unknown'}, "
            f"observed {observed_at}; missing claims remain unknown"
        ),
        provenance={
            "payload": payload_name,
            "raw_hash_field": hash_key,
            "raw_claims": dict(raw_claims),
        },
    )
    return envelope


def attestation_report(devices: list[dict]) -> dict:
    """Build a read-only tenant report from persisted DeviceState dictionaries."""
    rows = []
    invalid = 0
    for device in devices or []:
        if not isinstance(device, dict):
            continue
        raw = device.get("attestation")
        if not isinstance(raw, dict):
            continue
        try:
            envelope = envelope_from_dict(raw)
        except Exception:
            invalid += 1
            continue
        item = envelope.to_dict()
        item["device_id"] = device.get("device_id") or envelope.subject
        item["name"] = device.get("name") or None
        item["platform"] = device.get("platform") or None
        rows.append(item)
    rows.sort(key=lambda row: (row.get("source") or "", row.get("subject") or ""))
    return {
        "model_version": MODEL_VERSION,
        "total": len(rows),
        "invalid": invalid,
        "attestations": rows,
        "explanation": "Read-only neutral attestation envelopes; absent claims are unknown, not false.",
    }
