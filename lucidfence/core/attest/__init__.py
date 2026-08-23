"""Device-attestation verification package — local-verifiable perimeter.

This package implements the local-verifiable core of the multi-UEM attestation
cluster (dictamen t_5c3d21dd, card t_44445e00). It verifies *raw* attestation
blobs from Apple MDA, Android Key Attestation, and Windows TPM quotes using only
stdlib + ``cryptography`` (already a dependency), against **vendored** trust
roots, with nonce binding (anti-replay via ``NonceCache``) and a 4-state verdict
(``VERIFIED | UNVERIFIED | UNKNOWN | REJECTED`` — never a bool).

Out of scope (external gaps, dictamen C6-C8): Play Integrity verdict (Google
API), DHA "healthy" judgement (golden-PCR DB), and enrollment/bootstrap
(SCEP/MDM).

Red line #110: the product MUST only render "Verified" when
``AttestationState.VERIFIED``. See ``types.AttestationState.is_trusted`` and the
``test_render_gate`` assertions.
"""
from __future__ import annotations

from typing import Iterable, Optional

from cryptography import x509

from .android import verify_android_attestation
from .apple import verify_apple_attestation
from .common import (
    cert_is_valid_at,
    der_extract_octet_strings,
    iter_certificates,
    verify_chain_to_root,
)
from .nonce import NonceCache
from .reconcile import reconcile_identity
from .types import (
    AttestationState,
    DeviceAttestation,
    Provider,
    Reconciliation,
)
from .windows import verify_windows_attestation

__all__ = [
    "AttestationState",
    "DeviceAttestation",
    "Provider",
    "Reconciliation",
    "NonceCache",
    "verify_apple_attestation",
    "verify_android_attestation",
    "verify_windows_attestation",
    "verify_attestation",
    "reconcile_identity",
    "verify_chain_to_root",
    "cert_is_valid_at",
    "der_extract_octet_strings",
    "iter_certificates",
]


def verify_attestation(
    provider: str,
    blob: bytes,
    nonce: str,
    *,
    roots: Iterable[x509.Certificate],
    cache: Optional[NonceCache] = None,
    expected_device_id: Optional[str] = None,
    now=None,
    # Windows needs discrete fields (see verify_windows_attestation):
    aik_cert_der: Optional[bytes] = None,
    signed_quote: Optional[bytes] = None,
    signature: Optional[bytes] = None,
) -> DeviceAttestation:
    """Dispatch to the provider-specific verifier.

    ``provider`` is one of ``"apple" | "android" | "windows"``. For ``windows``,
    pass ``aik_cert_der``, ``signed_quote`` and ``signature`` instead of ``blob``.
    """
    p = provider.lower()
    if p == Provider.APPLE.value:
        return verify_apple_attestation(
            blob, nonce, roots=roots, cache=cache,
            expected_device_id=expected_device_id, now=now)
    if p == Provider.ANDROID.value:
        return verify_android_attestation(
            blob, nonce, roots=roots, cache=cache,
            expected_device_id=expected_device_id, now=now)
    if p == Provider.WINDOWS.value:
        if aik_cert_der is None or signed_quote is None or signature is None:
            # Import locally to avoid import cycle at module load.
            return DeviceAttestation(
                provider=Provider.WINDOWS, raw_blob=b"",
                verification_result=AttestationState.UNKNOWN,
                error="windows requires aik_cert_der+signed_quote+signature")
        return verify_windows_attestation(
            aik_cert_der=aik_cert_der, signed_quote=signed_quote,
            signature=signature, nonce=nonce, roots=roots, cache=cache,
            expected_device_id=expected_device_id, now=now)
    raise ValueError(f"unknown attestation provider: {provider}")
