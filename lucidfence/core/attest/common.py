"""Shared primitives for the device-attestation verifiers.

All verifiers operate on the *local-verifiable* perimeter described in the
feasibility dictamen (t_5c3d21dd): parse CMS/X.509 + chain-to-vendored-root +
nonce binding + signature check. Anything requiring an external service
(Play Integrity API, golden-PCR health DB, SCEP/MDM enrollment) is intentionally
out of scope and surfaces as ``UNKNOWN``/``REJECTED`` rather than a trusted
verdict.

The verification result is an enum, never a bool (red line #110):
``VERIFIED | UNVERIFIED | UNKNOWN | REJECTED``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa


def _is_ca(cert: x509.Certificate) -> bool:
    try:
        return bool(cert.extensions.get_extension_for_class(
            x509.BasicConstraints).value.ca)
    except x509.ExtensionNotFound:
        return False


def _verify_signature(issuer: x509.Certificate, cert: x509.Certificate) -> None:
    """Raise if ``cert`` is not signed by ``issuer``'s private key."""
    pub = issuer.public_key()
    alg = cert.signature_hash_algorithm
    if alg is None:
        raise ValueError("unsupported signature algorithm (none declared)")
    if isinstance(pub, rsa.RSAPublicKey):
        pub.verify(
            cert.signature, cert.tbs_certificate_bytes,
            padding.PKCS1v15(), alg,
        )
    elif isinstance(pub, ec.EllipticCurvePublicKey):
        pub.verify(
            cert.signature, cert.tbs_certificate_bytes,
            ec.ECDSA(alg),
        )
    else:
        raise ValueError(f"unsupported issuer key type: {type(pub).__name__}")


def _find_issuer(
    cert: x509.Certificate,
    by_subject: dict,
    root_by_subject: dict,
) -> x509.Certificate | None:
    target = cert.issuer
    for cand in list(root_by_subject.values()):
        if cand.subject == target:
            return cand
    for lst in by_subject.values():
        for cand in lst:
            if cand.subject == target:
                return cand
    return None


def verify_chain_to_root(
    presented: Sequence[x509.Certificate],
    root_certs: Sequence[x509.Certificate],
    *,
    now: datetime | None = None,
) -> tuple[bool, str, list[x509.Certificate]]:
    """Verify every link is signed by its issuer and the chain terminates at a
    trusted (vendored) root. Returns ``(ok, detail, chain)``.

    This is a manual, explicit chain walker (not ``x509.verification``) so the
    verdict is fully controllable: a missing root is ``UNKNOWN``, a broken
    signature is ``REJECTED``/``UNVERIFIED`` downstream, never a silent trust.
    """
    now = now or datetime.now(timezone.utc)
    if not root_certs:
        return False, "no_trusted_root_configured", []

    root_by_subject = {r.subject: r for r in root_certs}
    by_subject: dict = {}
    for c in presented:
        by_subject.setdefault(c.subject, []).append(c)

    leaves = [c for c in presented if not _is_ca(c)] or list(presented)
    for leaf in leaves:
        chain: list[x509.Certificate] = []
        cur = leaf
        for _ in range(len(presented) + 2):
            chain.append(cur)
            if cur.subject in root_by_subject:
                try:
                    _verify_signature(root_by_subject[cur.subject], cur)
                    return True, "chain_ok", chain
                except Exception:
                    pass
            issuer = _find_issuer(cur, by_subject, root_by_subject)
            if issuer is None:
                break
            try:
                _verify_signature(issuer, cur)
            except Exception:
                return False, "signature_invalid", chain
            cur = issuer
    return False, "no_path_to_trusted_root", []


def cert_is_valid_at(cert: x509.Certificate, now: datetime) -> tuple[bool, str]:
    """Check the leaf certificate validity window (freshness of the credential)."""
    try:
        not_before = cert.not_valid_before_utc
        not_after = cert.not_valid_after_utc
    except AttributeError:
        not_before = cert.not_valid_before.replace(tzinfo=timezone.utc)
        not_after = cert.not_valid_after.replace(tzinfo=timezone.utc)
    if now < not_before:
        return False, "cert_not_yet_valid"
    if now > not_after:
        return False, "cert_expired"
    return True, "ok"


def der_extract_octet_strings(data: bytes) -> list[bytes]:
    """Walk DER recursively and return the contents of every OCTET STRING.

    Used by the Android verifier to locate ``attestationChallenge`` inside the
    ``KeyDescription`` extension without a full ASN.1 schema parser (a
    documented spike approximation; full KeyDescription decode is future work).
    """
    out: list[bytes] = []

    def walk(buf: bytes) -> None:
        i = 0
        n = len(buf)
        while i < n:
            tag = buf[i]
            i += 1
            if (tag & 0x1F) == 0x1F:  # high-tag-number form
                while i < n and buf[i] & 0x80:
                    i += 1
                i += 1
            if i >= n:
                break
            length = buf[i]
            i += 1
            if length & 0x80:
                num = length & 0x7F
                length = int.from_bytes(buf[i:i + num], "big")
                i += num
            if i + length > n:
                break
            content = buf[i:i + length]
            if tag == 0x04:  # OCTET STRING
                out.append(content)
            if tag & 0x20:  # constructed -> recurse
                walk(content)
            i += length

    walk(data)
    return out


def iter_certificates(blobs: Iterable[bytes]) -> list[x509.Certificate]:
    certs: list[x509.Certificate] = []
    for b in blobs:
        try:
            certs.append(x509.load_der_x509_certificate(b))
        except Exception:
            try:
                certs.append(x509.load_pem_x509_certificate(b))
            except Exception:
                continue
    return certs
