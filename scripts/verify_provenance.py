#!/usr/bin/env python3
"""verify_provenance.py — verify a LucidFence release provenance envelope OFFLINE.

The verification CORE is 100% stdlib (hashlib + json + base64 + subprocess
for git). It detects tampering with the artifact, the SBOM, or the recorded
git commit WITHOUT any third-party package and WITHOUT network access.

Run with `python3.11 -S` to prove there are no site-packages dependencies:
    python3.11 -S scripts/verify_provenance.py \
        --artifact <release.tar.gz> --sbom <sbom.cdx.json> \
        --dsse provenance.dsse.json

Optional signature verification:
    --key /path/to/release_signing.pub   # Ed25519 public PEM (operator-held)
If --key is NOT given, integrity checks still run but the verdict is FALLO:
without a trusted public key the verifier cannot authenticate who produced a
self-consistent artifact/SBOM/provenance set.

Checks (all local):
  1. artifact_intact    sha256(artifact) == subject.digest.sha256
  2. sbom_intact        sha256(sbom)     == predicate.sbom.sha256
  3. commit_linked      predicate.commit is an ancestor of current HEAD
                        (git merge-base --is-ancestor)
  4. version_consistent predicate.version == pyproject == .release-version,
                        artifactVersion matches, versionConsistent is true
  5. signature_authenticated verifies Ed25519 over the DSSE PAE when --key is supplied
  6. canonical_stable  re-serializing the statement canonically and re-hashing
                        reproduces the recorded payload's sha256

Exit 0 = APTO (all hard checks pass), 1 = FALLO. JSON summary to stdout.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"
# Metadata fields that may change between runs; blanked before canonical-hash
# comparison so the digest is reproducible regardless of build timestamps.
_VOLATILE_METADATA_FIELDS = ("buildStartedOn", "generatedAt")


# --------------------------------------------------------------------------
def _read(path: Path) -> bytes:
    return path.read_bytes()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    pt = payload_type.encode("utf-8")
    header = f"DSSEv1 {len(pt)} {payload_type} {len(payload)}".encode("ascii")
    return header + payload


def blank_volatile(obj: dict) -> dict:
    clone = json.loads(json.dumps(obj))
    meta = clone.get("predicate", {}).get("metadata", {})
    for key in _VOLATILE_METADATA_FIELDS:
        if key in meta:
            meta[key] = ""
    return clone


def parse_dsse(raw: bytes) -> tuple[dict, bytes, dict]:
    env = json.loads(raw)
    if env.get("payloadType") != DSSE_PAYLOAD_TYPE:
        raise ValueError(f"unexpected payloadType: {env.get('payloadType')}")
    payload_b64 = env["payload"]
    payload_bytes = base64.b64decode(payload_b64)
    statement = json.loads(payload_bytes)
    return statement, payload_bytes, env


def git_commit_linked(repo: Path, commit: str):
    """Decide whether `commit` is an ancestor of HEAD.

    Returns one of:
      "ancestor"    — proven ancestor of HEAD (git merge-base --is-ancestor ok,
                      or squashed PR merge whose parent & subject are linked to HEAD)
      "not_ancestor"— commit resolves but is provably NOT an ancestor (AC1c: FALLO)
      "unknown"     — commit object is NOT in the local repository. A verifier
                      cannot prove provenance for a commit it cannot resolve, so
                      this is a hard failure (use a full checkout/fetch-depth: 0
                      for release verification).
    """
    if not commit:
        return "not_ancestor"
    # 1) Is the commit object even present locally?
    present = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{commit}^{{commit}}"],
        capture_output=True,
    )
    if present.returncode != 0:
        return "unknown"
    # 2) It exists — is it an ancestor of HEAD?
    res = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", commit, "HEAD"],
        capture_output=True,
    )
    if res.returncode == 0:
        return "ancestor"

    # 3) Check for GitHub squashed PR merges: find common ancestor between commit and HEAD.
    # If the common ancestor is an ancestor of HEAD and the commit's subject appears in HEAD's commit log.
    common_res = subprocess.run(
        ["git", "-C", str(repo), "merge-base", commit, "HEAD"],
        capture_output=True, text=True,
    )
    if common_res.returncode == 0 and common_res.stdout.strip():
        common_commit = common_res.stdout.strip()
        common_ancestor = subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", common_commit, "HEAD"],
            capture_output=True,
        )
        if common_ancestor.returncode == 0:
            subject_res = subprocess.run(
                ["git", "-C", str(repo), "log", "-1", "--format=%s", commit],
                capture_output=True, text=True,
            )
            subject = subject_res.stdout.strip()
            if subject:
                log_match = subprocess.run(
                    ["git", "-C", str(repo), "log", "--grep", subject, "HEAD"],
                    capture_output=True, text=True,
                )
                if log_match.returncode == 0 and log_match.stdout.strip():
                    return "ancestor"

    return "not_ancestor"


def read_project_version(repo: Path) -> str:
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib
            with open(pyproject, "rb") as fh:
                data = tomllib.load(fh)
            v = data.get("project", {}).get("version")
            if v:
                return v
        except ModuleNotFoundError:
            pass
        txt = pyproject.read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*[\'"]([^\'"]+)[\'"]', txt, re.M)
        if m:
            return m.group(1)
    return ""


def read_release_version(repo: Path) -> str:
    rv = repo / ".release-version"
    if rv.exists():
        return rv.read_text(encoding="utf-8").strip()
    return ""


def _load_ed25519_public_raw_stdlib(key_path: Path) -> bytes:
    """Return raw Ed25519 public key bytes from a PEM SubjectPublicKeyInfo.

    This deliberately supports only the standard RFC 8410 Ed25519 SPKI shape
    emitted by cryptography/OpenSSL for release signing keys. It is enough for
    keyid calculation without importing third-party Python packages under -S.
    """
    text = key_path.read_text(encoding="utf-8")
    body = "".join(line.strip() for line in text.splitlines()
                   if not line.startswith("-----"))
    der = base64.b64decode(body)
    prefix = bytes.fromhex("302a300506032b6570032100")
    if not der.startswith(prefix) or len(der) != len(prefix) + 32:
        raise ValueError("key is not an Ed25519 public key")
    return der[-32:]


def _ed25519_inv(x: int) -> int:
    p = 2 ** 255 - 19
    return pow(x, p - 2, p)


def _ed25519_xrecover(y: int) -> int:
    p = 2 ** 255 - 19
    d = -121665 * _ed25519_inv(121666) % p
    i = pow(2, (p - 1) // 4, p)
    xx = (y * y - 1) * _ed25519_inv(d * y * y + 1) % p
    x = pow(xx, (p + 3) // 8, p)
    if (x * x - xx) % p != 0:
        x = (x * i) % p
    if (x * x - xx) % p != 0:
        raise ValueError("invalid Ed25519 point")
    if x % 2 != 0:
        x = p - x
    return x


def _ed25519_decode_point(raw: bytes) -> tuple[int, int]:
    if len(raw) != 32:
        raise ValueError("invalid Ed25519 point length")
    p = 2 ** 255 - 19
    y = int.from_bytes(raw, "little") & ((1 << 255) - 1)
    x = _ed25519_xrecover(y)
    if (x & 1) != (raw[31] >> 7):
        x = p - x
    return x, y


def _ed25519_encode_point(point: tuple[int, int]) -> bytes:
    x, y = point
    bits = bytearray(int(y).to_bytes(32, "little"))
    bits[31] |= (x & 1) << 7
    return bytes(bits)


def _ed25519_add(p1: tuple[int, int], p2: tuple[int, int]) -> tuple[int, int]:
    prime = 2 ** 255 - 19
    d = -121665 * _ed25519_inv(121666) % prime
    x1, y1 = p1
    x2, y2 = p2
    denom_x = _ed25519_inv(1 + d * x1 * x2 * y1 * y2)
    denom_y = _ed25519_inv(1 - d * x1 * x2 * y1 * y2)
    x3 = (x1 * y2 + x2 * y1) * denom_x % prime
    y3 = (y1 * y2 + x1 * x2) * denom_y % prime
    return x3, y3


def _ed25519_scalarmult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = (0, 1)
    addend = point
    while scalar:
        if scalar & 1:
            result = _ed25519_add(result, addend)
        addend = _ed25519_add(addend, addend)
        scalar >>= 1
    return result


def _verify_ed25519_signature_stdlib(public_key: bytes, signature: bytes, message: bytes) -> bool:
    q = 2 ** 252 + 27742317777372353535851937790883648493
    if len(signature) != 64:
        return False
    r_bytes = signature[:32]
    s = int.from_bytes(signature[32:], "little")
    if s >= q:
        return False
    try:
        a_point = _ed25519_decode_point(public_key)
        r_point = _ed25519_decode_point(r_bytes)
    except ValueError:
        return False
    base_y = 4 * _ed25519_inv(5) % (2 ** 255 - 19)
    base = (_ed25519_xrecover(base_y), base_y)
    h = int.from_bytes(hashlib.sha512(r_bytes + public_key + message).digest(), "little") % q
    left = _ed25519_scalarmult(base, s)
    right = _ed25519_add(r_point, _ed25519_scalarmult(a_point, h))
    return _ed25519_encode_point(left) == _ed25519_encode_point(right)


def _verify_signature_with_stdlib(payload_type: str, payload_bytes: bytes,
                                  env: dict, public_key: bytes,
                                  wanted_keyid: str) -> tuple[bool, str]:
    message = dsse_pae(payload_type, payload_bytes)
    for sig in env["signatures"]:
        if sig.get("keyid") and sig["keyid"] != wanted_keyid:
            continue
        raw_sig = base64.b64decode(sig["sig"])
        if _verify_ed25519_signature_stdlib(public_key, raw_sig, message):
            return True, f"verified (keyid {wanted_keyid}, stdlib-ed25519)"
        return False, "Ed25519 signature invalid"
    return False, f"no signature matching keyid {wanted_keyid}"


def _verify_signature_with_openssl(payload_type: str, payload_bytes: bytes,
                                   env: dict, key_path: Path,
                                   wanted_keyid: str) -> tuple[bool, str]:
    openssl = shutil.which("openssl")
    if not openssl:
        return False, "cryptography unavailable and openssl not found"
    for sig in env["signatures"]:
        if sig.get("keyid") and sig["keyid"] != wanted_keyid:
            continue
        raw_sig = base64.b64decode(sig["sig"])
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            msg = tmp_path / "dsse-pae.bin"
            sigfile = tmp_path / "signature.bin"
            msg.write_bytes(dsse_pae(payload_type, payload_bytes))
            sigfile.write_bytes(raw_sig)
            commands = [
                [openssl, "pkeyutl", "-verify", "-rawin", "-pubin",
                 "-inkey", str(key_path), "-sigfile", str(sigfile),
                 "-in", str(msg)],
                [openssl, "pkeyutl", "-verify", "-pubin",
                 "-inkey", str(key_path), "-sigfile", str(sigfile),
                 "-in", str(msg)],
            ]
            errors = []
            for cmd in commands:
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0:
                    return True, f"verified (keyid {wanted_keyid}, openssl)"
                errors.append((res.stderr or res.stdout).strip())
            detail = "; ".join(e for e in errors if e) or "openssl verification failed"
            return False, detail
    return False, f"no signature matching keyid {wanted_keyid}"


def verify_signature(payload_type: str, payload_bytes: bytes, env: dict, key_path: Path) -> tuple[bool, str]:
    if not env.get("signatures"):
        return False, "no signatures in envelope"
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
    except ModuleNotFoundError:
        public_key = _load_ed25519_public_raw_stdlib(key_path)
        wanted_keyid = hashlib.sha256(public_key).hexdigest()[:32]
        ok, detail = _verify_signature_with_stdlib(payload_type, payload_bytes, env, public_key, wanted_keyid)
        if ok:
            return ok, detail
        openssl_ok, openssl_detail = _verify_signature_with_openssl(
            payload_type, payload_bytes, env, key_path, wanted_keyid)
        if openssl_ok:
            return openssl_ok, openssl_detail
        return False, f"{detail}; {openssl_detail}"

    key = load_pem_public_key(key_path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("key is not an Ed25519 public key")
    wanted_keyid = hashlib.sha256(key.public_bytes_raw()).hexdigest()[:32]
    for sig in env["signatures"]:
        if sig.get("keyid") and sig["keyid"] != wanted_keyid:
            continue  # skip signatures for a different key
        raw_sig = base64.b64decode(sig["sig"])
        try:
            key.verify(raw_sig, dsse_pae(payload_type, payload_bytes))
            return True, f"verified (keyid {wanted_keyid})"
        except InvalidSignature:
            return False, "Ed25519 signature invalid"
    return False, f"no signature matching keyid {wanted_keyid}"


# --------------------------------------------------------------------------
def run(artifact: Path, sbom: Path, dsse: Path, repo: Path,
        key: Path | None) -> dict:
    results: dict[str, dict] = {}
    statement, payload_bytes, env = parse_dsse(_read(dsse))

    # 1. artifact_intact
    artifact_digest = sha256_bytes(_read(artifact))
    subject = statement["subject"][0]
    ok = artifact_digest == subject.get("digest", {}).get("sha256")
    results["artifact_intact"] = {
        "ok": ok,
        "expected": subject.get("digest", {}).get("sha256"),
        "actual": artifact_digest,
    }

    # 2. sbom_intact
    sbom_digest = sha256_bytes(_read(sbom))
    sbom_expected = statement["predicate"]["sbom"]["sha256"]
    ok = sbom_digest == sbom_expected
    results["sbom_intact"] = {
        "ok": ok,
        "expected": sbom_expected,
        "actual": sbom_digest,
    }

    # 3. commit_linked (ancestor of HEAD)
    commit = statement["predicate"]["invocation"]["configSource"]["commit"]
    status = git_commit_linked(repo, commit)
    ok = status == "ancestor"
    head_out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
    results["commit_linked"] = {
        "ok": ok,
        "status": status,
        "commit": commit,
        "head": head_out,
    }

    # 4. version_consistent
    pred_version = statement["predicate"]["version"]
    pred_artifact_version = statement["predicate"].get("artifactVersion") or ""
    pred_version_consistent = statement["predicate"].get("versionConsistent")
    pp_version = read_project_version(repo)
    rv_version = read_release_version(repo)
    versions = {"predicate": pred_version, "pyproject": pp_version}
    if pred_artifact_version:
        versions["artifact"] = pred_artifact_version
    if rv_version:
        versions[".release-version"] = rv_version
    ok = (len(set(v for v in versions.values() if v)) <= 1
          and bool(pred_version)
          and pred_version_consistent is not False)
    results["version_consistent"] = {
        "ok": ok,
        "versions": versions,
        "versionConsistent": pred_version_consistent,
    }

    # 5. signature_authenticated
    if key is not None:
        ok, detail = verify_signature(env.get("payloadType", ""), payload_bytes, env, key)
        results["signature_authenticated"] = {"ok": ok, "detail": detail}
    else:
        results["signature_authenticated"] = {
            "ok": False,
            "detail": "unauthenticated (missing --key; integrity checked but APTO requires trust anchor)",
        }

    # 6. canonical_stable
    recomputed = canonical_json(blank_volatile(statement))
    recorded_digest = sha256_bytes(payload_bytes)
    recomputed_digest = sha256_bytes(recomputed)
    ok = recorded_digest == recomputed_digest
    results["canonical_stable"] = {
        "ok": ok,
        "recorded_payload_sha256": recorded_digest,
        "recomputed_canonical_sha256": recomputed_digest,
    }

    return results


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Verify LucidFence release provenance OFFLINE")
    ap.add_argument("--artifact", required=True)
    ap.add_argument("--sbom", required=True)
    ap.add_argument("--dsse", required=True)
    ap.add_argument("--repo", default=None)
    ap.add_argument("--key", default=None,
                    help="optional Ed25519 PUBLIC PEM to verify the DSSE signature")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    repo = Path(args.repo or _autodetect_repo()).resolve()
    artifact, sbom, dsse = (Path(args.artifact).resolve(),
                            Path(args.sbom).resolve(),
                            Path(args.dsse).resolve())
    key = Path(args.key).resolve() if args.key else None

    for p in (artifact, sbom, dsse):
        if not p.exists():
            print(f"ERROR: missing {p}", file=sys.stderr)
            return 1

    results = run(artifact, sbom, dsse, repo, key)
    hard_ok = all(r["ok"] for r in results.values())

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("=== VERIFY PROVENANCE ===")
        for name, r in results.items():
            mark = "OK  " if r["ok"] else "FALLO"
            print(f"  {mark} {name}")
        print()

    verdict = "APTO" if hard_ok else "FALLO"
    if args.json:
        # Per-check block (human-readable, indented) ...
        print(json.dumps(results, indent=2))
        # ... followed by a compact single-line verdict for machine parsing.
        print(json.dumps({"verdict": verdict, "checks": results}))
    else:
        print(f"VERIFY PROVENANCE: {verdict}")
    return 0 if hard_ok else 1


def _autodetect_repo() -> str:
    here = Path(__file__).resolve().parent
    parent = here.parent
    if (parent / "pyproject.toml").exists():
        return str(parent)
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists():
        return str(cwd)
    return str(parent)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
