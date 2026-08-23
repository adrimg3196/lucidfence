"""Windows Device Health Attestation — TPM quote verifier (local-verifiable core, C1).

What is verified locally (dictamen §1C / C1):
  * The TPM ``quote`` (TPMS_ATTEST) + signature are signed by an Attestation
    Identity Key (AIK), and the AIK certificate chains to a *vendored*
    Microsoft/TPM root (no external lookup).
  * The signature over the quote is cryptographically valid under the AIK
    public key (``signature over PCRs + nonce`` check).
  * The quote's ``extraData`` (the qualifying data) equals the nonce we
    issued (nonce binding / anti-replay).

What is NOT done here (out of scope, C8):
  * Judging the device \"healthy\" requires a *golden-PCR* database (known-good
    boot measurements) that is OEM/model-specific and NOT public. This verifier
    confirms the quote is **authentic** (a real TPM signed these PCRs), never
    that the PCRs are *good*. A \"healthy\" verdict is an external dependency.
  * The DHA service (Intune/ConfigMgr) is an external authority; we validate a
    blob we receive, we do not call Microsoft.

TPM quote structure: a production TPM2 quote is ``TPMS_ATTEST`` (a fixed-format
TPM structure) plus a ``TPMT_SIGNATURE``. cryptography has no TPM wire-format
parser and adding one would pull in a TPM dependency (out of scope). This
verifier therefore defines a **documented spike quote container** — a DER
SEQUENCE of {``extraData`` OCTET STRING (the nonce), ``pcr_digest`` OCTET STRING}
— that the AIK signs. The trust boundary implemented (chain-to-vendored-root +
signature-over-quote + nonce-bound extraData) is exactly the local-verifiable
core; swapping the container parser for a real ``TPMS_ATTEST`` decoder is future
work and does not change that boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

from .common import cert_is_valid_at, verify_chain_to_root
from .nonce import NonceCache
from .types import AttestationState, DeviceAttestation, Provider


def _parse_quote_container(signed_quote: bytes) -> tuple[Optional[bytes], Optional[bytes], str]:
    """Parse the documented spike quote container (DER SEQUENCE of OCTET STRINGs).

    Layout: SEQUENCE { extraData OCTET STRING, pcrDigest OCTET STRING }.
    Returns ``(extra_data, pcr_digest, detail)``.
    """
    from .common import der_extract_octet_strings
    octets = der_extract_octet_strings(signed_quote)
    if len(octets) < 2:
        return None, None, "quote_container_malformed"
    return octets[0], octets[1], "ok"


def _verify_quote_signature(aik: x509.Certificate, signed_quote: bytes,
                            signature: bytes) -> tuple[bool, str]:
    pub = aik.public_key()
    try:
        if isinstance(pub, rsa.RSAPublicKey):
            pub.verify(signature, signed_quote, padding.PKCS1v15(), hashes.SHA256())
        elif isinstance(pub, ec.EllipticCurvePublicKey):
            pub.verify(signature, signed_quote, ec.ECDSA(hashes.SHA256()))
        else:
            return False, "unsupported_aik_key_type"
        return True, "ok"
    except Exception as e:
        return False, f"signature_invalid:{type(e).__name__}"


def verify_windows_attestation(
    *,
    aik_cert_der: bytes,
    signed_quote: bytes,
    signature: bytes,
    nonce: str,
    roots: Iterable[x509.Certificate],
    cache: Optional[NonceCache] = None,
    expected_device_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> DeviceAttestation:
    now = now or datetime.now(timezone.utc)
    # We keep raw_blob as the concatenation for audit; documented as the quote set.
    raw = aik_cert_der + signed_quote + signature
    result = DeviceAttestation(provider=Provider.WINDOWS, raw_blob=raw,
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

    # 1. Parse AIK cert.
    try:
        aik = x509.load_der_x509_certificate(aik_cert_der)
    except Exception:
        result.verification_result = AttestationState.UNKNOWN
        result.error = "aik_cert_unparseable"
        result.evidence_refs.append("parse:aik_cert_unparseable")
        return result

    # 2. AIK chain -> vendored root.
    ok, detail, chain = verify_chain_to_root([aik], roots_list, now=now)
    if not ok:
        result.evidence_refs.append(f"chain:{detail}")
        result.verification_result = (
            AttestationState.UNKNOWN if detail == "no_trusted_root_configured"
            else AttestationState.UNVERIFIED)
        result.error = detail
        return result
    result.evidence_refs.append("chain:ok->vendored_root")

    # 3. AIK validity window.
    valid, vdetail = cert_is_valid_at(aik, now)
    if not valid:
        result.evidence_refs.append(f"aik_validity:{vdetail}")
        result.verification_result = AttestationState.UNVERIFIED
        result.error = vdetail
        return result

    # 4. Signature over the quote (PCRs + nonce) with the AIK public key.
    sig_ok, sig_detail = _verify_quote_signature(aik, signed_quote, signature)
    if not sig_ok:
        result.evidence_refs.append(f"quote_signature:{sig_detail}")
        result.verification_result = AttestationState.REJECTED
        result.error = sig_detail
        return result
    result.evidence_refs.append("quote_signature:ok")

    # 5. Nonce binding via quote extraData.
    extra_data, pcr_digest, qdetail = _parse_quote_container(signed_quote)
    if qdetail != "ok" or extra_data is None or pcr_digest is None:
        result.evidence_refs.append(f"quote:{qdetail}")
        result.verification_result = AttestationState.UNVERIFIED
        result.error = qdetail
        return result
    if extra_data != nonce.encode("ascii"):
        result.evidence_refs.append("nonce:binding_mismatch(extraData)")
        result.verification_result = AttestationState.REJECTED
        result.error = "quote_extraData!=nonce"
        return result
    result.evidence_refs.append("nonce:bound(extraData)")

    result.device_id = expected_device_id
    result.parsed_claims = {
        "aik_subject": aik.subject.rfc4514_string(),
        "aik_serial": str(aik.serial_number),
        "issuer": aik.issuer.rfc4514_string(),
        "pcr_digest_present": pcr_digest is not None,
        # NOTE C8: authenticity != health. We never assert known-good PCRs.
        "health_judged": False,
    }
    result.verification_result = AttestationState.VERIFIED
    return result
