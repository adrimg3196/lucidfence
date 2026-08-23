"""Android Key Attestation verifier — local-verifiable perimeter (C1).

What is verified locally (dictamen §1B / C1):
  * The blob (a DER-encoded X.509 certificate chain) anchors to a *vendored*
    Google hardware key-attestation root.
  * The ``KeyDescription`` extension (OID ``1.3.6.1.4.1.11129.2.17``) is present
    on the leaf and carries ``attestationChallenge``.
  * ``attestationChallenge`` == the nonce we issued (nonce binding / anti-replay).
  * The leaf certificate validity window covers ``now``.

What is NOT done here (out of scope, C6-C7):
  * Play Integrity verdict — that is a *remote* attestation signed by Google and
    requires calling Google's API. This verifier only handles the local,
    hardware-backed **Key Attestation** path. A Play Integrity claim is a
    separate, external gap.

KeyDescription decoding: a full parse needs the ASN.1 schema (SEQUENCE of
AttestationApplicationId, teeEnforced/softwareEnforced AuthorizationList, keymaster
version, etc.). For this spike we use a documented approximation: we extract every
OCTET STRING inside the extension via a recursive DER walk and check that the
``attestationChallenge`` octet equals ``nonce``. Full ``AuthorizationList``
decoding (teeEnforced flags, os_version, patch level) is future work and does not
change the local-verify trust boundary — only adds richer claims.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Iterable, Optional

from cryptography import x509

from .common import cert_is_valid_at, der_extract_octet_strings, verify_chain_to_root
from .nonce import NonceCache
from .types import AttestationState, DeviceAttestation, Provider

KEY_DESCRIPTION_OID = x509.ObjectIdentifier("1.3.6.1.4.1.11129.2.17")


def _decode_blob(blob: bytes) -> list[x509.Certificate]:
    """Decode an Android attestation blob: either a single DER chain blob, a
    concatenated DER chain, or a PEM bundle.
    """
    certs: list[x509.Certificate] = []
    # Try whole-blob DER chain (Android often concatenates DER certs).
    try:
        certs.append(x509.load_der_x509_certificate(blob))
    except Exception:
        pass
    if not certs:
        try:
            certs.append(x509.load_pem_x509_certificate(blob))
        except Exception:
            pass
    if certs:
        return certs
    # Concatenated DER: slide a window.
    i = 0
    n = len(blob)
    while i < n:
        try:
            c = x509.load_der_x509_certificate(blob[i:])
            certs.append(c)
            i += len(c.public_bytes(x509.Encoding.DER))
        except Exception:
            i += 1
            if not certs:
                break
    return certs


def _find_challenge(leaf: x509.Certificate, nonce: str) -> tuple[bool, list[bytes]]:
    try:
        ext = leaf.extensions.get_extension_for_oid(KEY_DESCRIPTION_OID)
    except x509.ExtensionNotFound:
        return False, []
    raw = ext.value.value if isinstance(ext.value, x509.UnrecognizedExtension) else getattr(ext.value, "value", None)
    if not raw:
        return False, []
    octets = der_extract_octet_strings(bytes(raw))
    nonce_bytes = nonce.encode("ascii")
    return nonce_bytes in octets, octets


def verify_android_attestation(
    blob: bytes,
    nonce: str,
    *,
    roots: Iterable[x509.Certificate],
    cache: Optional[NonceCache] = None,
    expected_device_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> DeviceAttestation:
    now = now or datetime.now(timezone.utc)
    result = DeviceAttestation(provider=Provider.ANDROID, raw_blob=blob,
                               device_id=expected_device_id)
    roots_list = list(roots)

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

    certs = _decode_blob(blob)
    if not certs:
        result.verification_result = AttestationState.UNKNOWN
        result.error = "no_certificates_in_blob"
        result.evidence_refs.append("parse:no_certificates")
        return result
    result.evidence_refs.append(f"parse:{len(certs)}_certs")

    ok, detail, chain = verify_chain_to_root(certs, roots_list, now=now)
    if not ok:
        result.evidence_refs.append(f"chain:{detail}")
        result.verification_result = (
            AttestationState.UNKNOWN if detail == "no_trusted_root_configured"
            else AttestationState.UNVERIFIED)
        result.error = detail
        return result
    result.evidence_refs.append("chain:ok->vendored_root")

    valid, vdetail = cert_is_valid_at(chain[0], now)
    if not valid:
        result.evidence_refs.append(f"leaf_validity:{vdetail}")
        result.verification_result = AttestationState.UNVERIFIED
        result.error = vdetail
        return result

    bound, _octets = _find_challenge(chain[0], nonce)
    if not bound:
        result.evidence_refs.append("nonce:binding_mismatch(attestationChallenge)")
        result.verification_result = AttestationState.REJECTED
        result.error = "attestationChallenge!=nonce"
        return result
    result.evidence_refs.append("nonce:bound(attestationChallenge)")

    result.device_id = expected_device_id
    result.parsed_claims = {
        "leaf_subject": chain[0].subject.rfc4514_string(),
        "leaf_serial": str(chain[0].serial_number),
        "issuer": chain[0].issuer.rfc4514_string(),
        "chain_len": len(chain),
        "key_description_oid": "1.3.6.1.4.1.11129.2.17",
    }
    result.verification_result = AttestationState.VERIFIED
    return result
