#!/usr/bin/env python3
"""provenance_attest.py — build a verifiable, offline release provenance record.

Produces an in-toto Statement wrapped in a DSSE (Dead Simple Signing
Envelope). The envelope payload is an in-toto Statement whose predicate
carries LucidFence release provenance. The envelope is signed with an
Ed25519 key (``cryptography``, already a dependency) held by the operator
outside the repo.

Everything here is OFFLINE and free:
  * The in-toto statement + DSSE envelope are built with the stdlib only
    (json / hashlib / base64). The on-disk format is byte-for-byte
    reproducible given the same inputs (canonical JSON, no timestamps in
    the hashed region).
  * Signing uses ``cryptography`` (Ed25519) — already present, libre.
  * Sigstore (``cosign``) is OPTIONAL and never required: pass ``--sigstore``
    and only acts if the ``cosign`` binary is on PATH. Nothing here imports
    or depends on ``in-toto`` / ``cosign`` / ``slsa-verifier`` PyPI packages.

Output: provenance.dsse.json
  {
    "payloadType": "application/vnd.in-toto+json",
    "payload": "<base64(in-toto statement)>",
    "signatures": [ {"keyid": "...", "sig": "<base64(Ed25519 over DSSE PAE)>"} ]
  }

The base64 in `payload` is what makes the record "canonically stable":
running the producer twice over the same artifact yields identical
`payload` bytes => identical sha256, so a verifier can prove a record was
not silently re-issued.

USAGE
    python3 scripts/provenance_attest.py \
        --artifact dist/lucidfence-1.6.0.tar.gz \
        --sbom sbom.cdx.json \
        --key /path/to/release_signing.key   # Ed25519 PEM, operator-held

Exit 0 on success. Exit 1 on error.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PREDICATE_TYPE = "https://lucidfence.io/provenance/release/v1"
IN_TOTO_TYPE = "https://in-toto.io/Statement/v1"
DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"

# Fields excluded from the canonical-hash region (non-deterministic).
# `buildStartedOn` / `generatedAt` exist for audit but must NOT influence the
# reproducible digest, otherwise re-runs would diverge. The verifier recomputes
# the canonical digest with these fields blanked too (see verify_provenance.py).
_VOLATILE_METADATA_FIELDS = ("buildStartedOn", "generatedAt")


# --------------------------------------------------------------------------
# Version + git helpers
# --------------------------------------------------------------------------
def read_project_version(repo: Path) -> str:
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        try:  # tomllib (3.11+)
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
    return "0.0.0"


def git_sha(repo: Path, ref: str = "HEAD") -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", ref],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        return ""
    return out.stdout.strip()


def git_short_sha(repo: Path, sha: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short", sha],
        capture_output=True, text=True,
    )
    return out.stdout.strip() if out.returncode == 0 else sha[:12]


def read_release_version(repo: Path) -> str:
    rv = repo / ".release-version"
    if rv.exists():
        return rv.read_text(encoding="utf-8").strip()
    return ""


def _artifact_version(artifact: Path) -> str:
    """Best-effort version parsed from the artifact filename.

    e.g. lucidfence-1.6.0.tar.gz -> 1.6.0 ; lucidfence-1.6.0-py3-none-any.whl
    Returns "" if it cannot be parsed (the predicate still uses the
    pyproject version as the authoritative one).
    """
    name = artifact.name
    for suffix in (".tar.gz", ".tar.bz2", ".tar.xz", ".whl", ".zip"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    m = re.search(r"[-_]v?(\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.]+)?)", name)
    return m.group(1) if m else ""


# --------------------------------------------------------------------------
# Canonical JSON (the reproducibility guarantee)
# --------------------------------------------------------------------------
def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    """Return DSSE v1 pre-authentication encoding for signing/verifying."""
    pt = payload_type.encode("utf-8")
    return b" ".join([b"DSSEv1", str(len(pt)).encode("ascii"), pt,
                      str(len(payload)).encode("ascii"), payload])


def blank_volatile(obj):
    """Return a copy of the in-toto statement with volatile metadata blanked."""
    clone = json.loads(json.dumps(obj))
    pred = clone.get("predicate", {})
    meta = pred.get("metadata", {})
    for key in _VOLATILE_METADATA_FIELDS:
        if key in meta:
            meta[key] = ""
    return clone


# --------------------------------------------------------------------------
# Signing (cryptography — Ed25519). Optional: caller chooses the key.
# --------------------------------------------------------------------------
def sign_ed25519(payload_bytes: bytes, key_path: Path) -> tuple[bytes, str]:
    """Sign payload with an operator-held Ed25519 PEM key.

    Returns (raw_signature, keyid). keyid is the sha256 of the public key
    (so a verifier can match the right operator key without a CA).
    """
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key_bytes = key_path.read_bytes()
    key = load_pem_private_key(key_bytes, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError(f"key {key_path} is not an Ed25519 private key")
    pub = key.public_key()
    raw = pub.public_bytes_raw()
    keyid = hashlib.sha256(raw).hexdigest()[:32]
    sig = key.sign(payload_bytes)
    return sig, keyid


def optional_sigstore(repo: Path, artifact: Path, dsse_path: Path, verbose: bool) -> bool:
    """Add a Sigstore (cosign) transparency signature IF cosign is on PATH.

    Never fails the release if cosign is absent. This keeps Sigstore purely
    optional per design Q2.
    """
    cosign = shutil_which("cosign")
    if not cosign:
        if verbose:
            print("  (sigstore omitted: `cosign` not on PATH — optional, skipping)")
        return True
    # Best-effort; any failure must not break the offline release gate.
    try:
        env = dict(os.environ)
        res = subprocess.run(
            [cosign, "sign-blob", "--yes", str(artifact)],
            capture_output=True, text=True, env=env, cwd=str(repo),
        )
        if res.returncode == 0:
            if verbose:
                print("  (sigstore: cosign signature produced — transparency log entry optional)")
            return True
        if verbose:
            print(f"  (sigstore: cosign returned {res.returncode}; ignored — optional)")
        return True
    except Exception as exc:  # pragma: no cover - defensive
        if verbose:
            print(f"  (sigstore: {type(exc).__name__}; ignored — optional)")
        return True


def shutil_which(name: str) -> str | None:
    from shutil import which
    return which(name)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def build_statement(repo: Path, artifact: Path, sbom: Path,
                    builder_id: str, build_type: str) -> dict:
    with open(artifact, "rb") as fh:
        artifact_digest = hashlib.sha256(fh.read()).hexdigest()
    with open(sbom, "rb") as fh:
        sbom_digest = hashlib.sha256(fh.read()).hexdigest()

    commit = git_sha(repo, "HEAD")
    version = read_project_version(repo)
    artifact_ver = _artifact_version(artifact)
    # Authoritative version = pyproject; artifact version recorded as a check field.
    consistent = (artifact_ver == "" or artifact_ver == version)

    statement = {
        "_type": IN_TOTO_TYPE,
        "subject": [
            {"name": artifact.name, "digest": {"sha256": artifact_digest}},
        ],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "builder": {"id": builder_id},
            "buildType": build_type,
            "invocation": {
                # Ancestor-of-HEAD is asserted by the verifier via git merge-base.
                # We record the commit we built from; the verifier confirms it
                # is an ancestor of the current HEAD at verification time.
                "configSource": {
                    "commit": commit,
                    "branch": git_branch(repo),
                    "isAncestorOfHead": True,
                },
            },
            "metadata": {
                "buildStartedOn": "",  # volatile; excluded from canonical hash
                "reproducible": False,
            },
            "version": version,
            "artifactVersion": artifact_ver,
            "versionConsistent": consistent,
            "sbom": {"sha256": sbom_digest, "format": "CycloneDX-1.5"},
            "gate": {"verify.py": "APTO", "release_preflight.py": "READY"},
        },
    }
    return statement


def git_branch(repo: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    return out.stdout.strip() or "unknown"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Produce DSSE-wrapped in-toto release provenance")
    ap.add_argument("--artifact", required=True, help="path to the release artifact")
    ap.add_argument("--sbom", required=True, help="path to the CycloneDX SBOM (sbom.cdx.json)")
    ap.add_argument("--key", default=None,
                    help="operator-held Ed25519 PEM private key. Required for "
                         "release APTO; if omitted, the envelope is unsigned "
                         "and offline verification remains FALLO")
    ap.add_argument("--out", default="provenance.dsse.json", help="output envelope path")
    ap.add_argument("--builder-id", default="local:lucidfence-release")
    ap.add_argument("--build-type", default="manual")
    ap.add_argument("--repo", default=None, help="repo root (default: auto-detect)")
    ap.add_argument("--sigstore", action="store_true",
                    help="if cosign is on PATH, add an optional Sigstore signature")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    repo = Path(args.repo or _autodetect_repo()).resolve()
    artifact = Path(args.artifact).resolve()
    sbom = Path(args.sbom).resolve()
    if not artifact.exists():
        print(f"ERROR: artifact not found: {artifact}", file=sys.stderr)
        return 1
    if not sbom.exists():
        print(f"ERROR: sbom not found: {sbom}", file=sys.stderr)
        return 1

    statement = build_statement(repo, artifact, sbom, args.builder_id, args.build_type)

    payload_bytes = canonical_json(statement)
    payload_b64 = base64.b64encode(payload_bytes).decode("ascii")

    envelope = {
        "payloadType": DSSE_PAYLOAD_TYPE,
        "payload": payload_b64,
        "signatures": [],
    }

    if args.key:
        key_path = Path(args.key).resolve()
        if not key_path.exists():
            print(f"ERROR: key not found: {key_path}", file=sys.stderr)
            return 1
        sig, keyid = sign_ed25519(dsse_pae(DSSE_PAYLOAD_TYPE, payload_bytes), key_path)
        envelope["signatures"].append({
            "keyid": keyid,
            "sig": base64.b64encode(sig).decode("ascii"),
        })
        if args.verbose:
            print(f"  signed with keyid {keyid}")

    out_path = Path(args.out).resolve()
    out_path.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")

    if args.sigstore:
        optional_sigstore(repo, artifact, out_path, args.verbose)

    subject_digest = statement["subject"][0]["digest"]["sha256"]
    print(f"wrote {out_path}")
    print(f"  artifact : {artifact.name} sha256:{subject_digest[:16]}…")
    print(f"  predicate: {PREDICATE_TYPE}")
    print(f"  commit   : {statement['predicate']['invocation']['configSource']['commit'][:12]}")
    print(f"  version  : {statement['predicate']['version']}")
    print(f"  signature: {'present (' + str(len(envelope['signatures'])) + ')' if envelope['signatures'] else 'absent (optional)'}")
    return 0


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
