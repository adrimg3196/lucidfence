"""Mock-blob builders for tests — generate REAL cryptographic artifacts.

These factories produce actual X.509 chains and signatures (using a throwaway
PKI) so the verifiers are exercised on valid, parseable, signable material
rather than hand-edited hex. The vendored roots are emitted alongside so tests
can pin them. Everything here is clearly labelled SPIKE/NOT-PRODUCTION.
"""
from __future__ import annotations

import datetime as dt
from typing import NamedTuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs7, Encoding
from cryptography.x509.oid import NameOID, ExtensionOID, ObjectIdentifier

_NOW = dt.datetime(2026, 8, 23, 12, 0, 0, tzinfo=dt.timezone.utc)
_NOT_AFTER = _NOW + dt.timedelta(days=3650)
_NOT_BEFORE = _NOW - dt.timedelta(days=1)

APPLE_NONCE_OID = ObjectIdentifier("1.2.840.113635.100.99.1")
ANDROID_KEYDESC_OID = ObjectIdentifier("1.3.6.1.4.1.11129.2.17")


class _Key(NamedTuple):
    key: rsa.RSAPrivateKey
    cert: x509.Certificate


def _mkkey() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _root(common_name: str) -> _Key:
    key = _mkkey()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOT_BEFORE).not_valid_after(_NOT_AFTER)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
        .sign(key, hashes.SHA256())
    )
    return _Key(key, cert)


def _inter(root: _Key, common_name: str) -> _Key:
    key = _mkkey()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(root.cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOT_BEFORE).not_valid_after(_NOT_AFTER)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
        .sign(root.key, hashes.SHA256())
    )
    return _Key(key, cert)


def build_apple_blob(nonce: str, device_serial: str = "ABC123SERIAL"):
    """Returns (blob_der, root_cert) for an Apple MDA mock blob.

    Signed leaf->root directly (mock PKI). The verifier's chain walker accepts
    a leaf whose issuer is a presented/vendored root, so a single root-signed
    certificate validates.
    """
    root = _root("Apple MDA Root (SPIKE)")
    leaf_key = _mkkey()
    leaf = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "Managed Device Identity"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, device_serial),
        ]))
        .issuer_name(root.cert.subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOT_BEFORE).not_valid_after(_NOT_AFTER)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.UnrecognizedExtension(APPLE_NONCE_OID, nonce.encode("ascii")),
                       critical=False)
        .sign(root.key, hashes.SHA256())
    )
    payload = (b'{"nonce":"' + nonce.encode("ascii") + b'","device_class":"macos"}')
    p7 = (pkcs7.PKCS7SignatureBuilder()
          .set_data(payload).add_signer(leaf, leaf_key, hashes.SHA256())
          .sign(Encoding.DER, [pkcs7.PKCS7Options.NoCapabilities]))
    return p7, root.cert


def build_android_blob(nonce: str, device_serial: str = "ANDROID99"):
    """Returns (blob_der, root_cert) for an Android Key Attestation mock blob.

    The leaf carries the KeyDescription extension (OID 1.3.6.1.4.1.11129.2.17)
    whose contents include the ``attestationChallenge`` octet (== nonce). Leaf
    is signed directly by the root (mock PKI).
    """
    root = _root("Google Hardware Attestation Root (SPIKE)")
    leaf_key = _mkkey()
    # KeyDescription approximation: an OCTET STRING containing the nonce.
    keydesc = x509.UnrecognizedExtension(
        ANDROID_KEYDESC_OID,
        # The recursive DER walk in common.der_extract_octet_strings will find
        # this OCTET STRING and match it against the nonce.
        b"\x04\x20" + nonce.encode("ascii")[:32].ljust(32, b"\x00"))
    leaf = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "Android Key Attestation"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, device_serial),
        ]))
        .issuer_name(root.cert.subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOT_BEFORE).not_valid_after(_NOT_AFTER)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(keydesc, critical=False)
        .sign(root.key, hashes.SHA256())
    )
    chain_der = leaf.public_bytes(Encoding.DER)
    return chain_der, root.cert


def build_windows_quote(nonce: str):
    """Returns (aik_cert_der, signed_quote_der, signature, root_cert).

    The AIK is signed directly by the mock Microsoft TPM root.
    """
    root = _root("Microsoft TPM AIK Root (SPIKE)")
    aik_key = _mkkey()
    aik = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "TPM AIK")]))
        .issuer_name(root.cert.subject)
        .public_key(aik_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOT_BEFORE).not_valid_after(_NOT_AFTER)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
        .sign(root.key, hashes.SHA256())
    )
    # Quote container: SEQUENCE { extraData OCTET STRING, pcrDigest OCTET STRING }
    extra = b"\x04\x20" + nonce.encode("ascii")[:32].ljust(32, b"\x00")
    pcrd = b"\x04\x20" + b"\x11" * 32
    quote = b"\x30\x44" + extra + pcrd
    signature = aik_key.sign(quote, padding.PKCS1v15(), hashes.SHA256())
    return (aik.public_bytes(Encoding.DER), quote, signature, root.cert)
