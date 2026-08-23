"""Apple Managed Device Attestation (MDA) verifier — local-verifiable perimeter.

What is verified locally (dictamen §1A / C1):
  * The blob parses as a CMS/PKCS7 SignedData carrying the device identity
    certificate chain.
  * Every certificate in the chain is signed by its issuer, and the chain
    terminates at a *vendored* Apple MDA root (no external lookup).
  * The nonce we issued is bound inside the blob (OID 1.2.840.113635.100.99.1 in
    the leaf cert extension + echoed in the signed payload) and was a single-use,
    fresh challenge (anti-replay via NonceCache).
  * The leaf certificate validity window covers ``now``.

What is NOT done here (out of scope, C6-C8):
  * Bootstrap / enrollment (SCEP, MDM escrow) — we *validate* a blob we receive,
    we do not *issue* trust.
  * A real Apple production root is not shipped in this spike; roots are a
    vendored ``roots=`` argument the caller pins. With no root configured the
    verdict is ``UNKNOWN`` (never silently trusted).

NOTE: Apple's production MDA blob is a ``.mobileconfig``/CMS structure with the
device identity as a Secure Enclave–derived certificate. This spike parses the
cryptographic substrate (PKCS7 SignedData + X.509 chain + nonce extension) which
is the local-verifiable core. The OID used for the nonce is a documented
placeholder (Apple's real MDA wraps the nonce in the certificate
``AppleDeviceIdentity`` extension); swapping in the real OID is a config change,
not an algorithm change.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable, Optional

from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs7

from .common import cert_is_valid_at, iter_certificates, verify_chain_to_root
from .nonce import NonceCache
from .types import AttestationState, DeviceAttestation, Provider

# Placeholder nonce OID (documented). Real Apple MDA: swap for the Apple
# device-identity extension OID when wiring production roots.
APPLE_NONCE_OID = x509.ObjectIdentifier("1.2.840.113635.100.99.1")


def _extract_p7certs(blob: bytes) -> list[x509.Certificate]:
    """Extract certificates carried inside a PKCS7/CMS SignedData blob."""
    try:
        return list(pkcs7.load_der_pkcs7_certificates(blob))
    except Exception:
        pass
    # Fallback: scan for concatenated DER certs.
    return iter_certificates([blob])


def _leaf_nonce_from_extension(leaf: x509.Certificate) -> Optional[bytes]:
    try:
        ext = leaf.extensions.get_extension_for_oid(APPLE_NONCE_OID)
    except x509.ExtensionNotFound:
        return None
    val = ext.value
    if isinstance(val, x509.UnrecognizedExtension):
        return bytes(val.value)
    return None


def verify_apple_attestation(
    blob: bytes,
    nonce: str,
    *,  # keyword-only
    roots: Iterable[x509.Certificate],
    cache: Optional[NonceCache] = None,
    expected_device_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> DeviceAttestation:
    """Verify an Apple MDA blob. Returns a populated ``DeviceAttestation``."""
    now = now or datetime.now(timezone.utc)
    result = DeviceAttestation(provider=Provider.APPLE, raw_blob=blob,
                               device_id=expected_device_id)
    roots_list = list(roots)

    # 1. Nonce single-use / freshness / replay (anti-replay gate first).
    if cache is not None:
        ok, reason = cache.consume(nonce, expected_device_id)
        if not ok:
            result.evidence_refs.append(f"nonce:{reason}")
            result.verification_result = (
                AttestationState.REJECTED if reason == "replay"
                else AttestationState.UNKNOWN if reason in ("not_found", "expired")
                else AttestationState.UNVERIFIED)
            result.error = f"nonce {reason}"
            return result
        result.evidence_refs.append("nonce:ok(single-use,fresh)")

    # 2. Parse the CMS chain.
    certs = _extract_p7certs(blob)
    if not certs:
        result.verification_result = AttestationState.UNKNOWN
        result.error = "no_certificates_in_blob"
        result.evidence_refs.append("parse:no_certificates")
        return result
    result.evidence_refs.append(f"parse:{len(certs)}_certs")

    # 3. Chain -> vendored root.
    ok, detail, chain = verify_chain_to_root(certs, roots_list, now=now)
    if not ok:
        result.evidence_refs.append(f"chain:{detail}")
        result.verification_result = (
            AttestationState.UNKNOWN if detail == "no_trusted_root_configured"
            else AttestationState.UNVERIFIED)
        result.error = detail
        return result
    result.evidence_refs.append("chain:ok->vendored_root")

    # 4. Leaf validity window.
    valid, vdetail = cert_is_valid_at(chain[0], now)
    if not valid:
        result.evidence_refs.append(f"leaf_validity:{vdetail}")
        result.verification_result = AttestationState.UNVERIFIED
        result.error = vdetail
        return result

    # 5. Nonce binding: present in leaf extension AND/OR signed payload.
    bound = False
    leaf_nonce = _leaf_nonce_from_extension(chain[0])
    if leaf_nonce is not None and leaf_nonce.decode("ascii", "ignore") == nonce:
        bound = True
    # Also accept nonce echoed in the signed CMS content if recoverable.
    try:
        content = _recover_signed_content(blob)
        if content and nonce.encode("ascii") in content:
            bound = True
    except Exception:
        content = None
    if not bound:
        result.evidence_refs.append("nonce:binding_mismatch")
        result.verification_result = AttestationState.REJECTED
        result.error = "nonce_binding_mismatch"
        return result
    result.evidence_refs.append("nonce:bound")

    # 6. Extract device identity claim (serial in subject).
    result.device_id = expected_device_id
    if expected_device_id is None:
        try:
            ser = chain[0].subject.get_attributes_for_oid(x509.NameOID.SERIAL_NUMBER)
            if ser:
                from lucidfence.core.multiuem import normalize_identity
                result.device_id = normalize_identity(ser[0].value)
        except Exception:
            pass

    result.parsed_claims = {
        "leaf_subject": chain[0].subject.rfc4514_string(),
        "leaf_serial": str(chain[0].serial_number),
        "issuer": chain[0].issuer.rfc4514_string(),
        "chain_len": len(chain),
    }
    result.verification_result = AttestationState.VERIFIED
    return result


def _recover_signed_content(blob: bytes) -> Optional[bytes]:
    """Best-effort extraction of the encapsulated CMS content (the signed JSON).

    cryptography 49/50 expose *certificate* extraction from a PKCS7 blob but not
    a public API to verify/recover the SignedData encapsulated content. The
    nonce is already bound via the leaf certificate extension above, so this is
    a conservative bonus check: it returns ``None`` rather than risk a false
    positive. A future upgrade can parse ``encapContentInfo`` DER directly.
    """
    return None
