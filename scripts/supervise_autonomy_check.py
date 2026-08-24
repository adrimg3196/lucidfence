#!/usr/bin/env python3
"""Create trusted receipts from black-box observations of ``saas_server.py``.

The supervisor never imports candidate code or gives it the receipt path or
run identity. Candidate code runs as an unprivileged HTTP server; only the
trusted parent observes its public loopback API and writes the context-bound
receipt.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import http.client
import json
import os
from pathlib import Path
import pwd
import re
import resource
import shutil
import signal
import socket
import stat
import subprocess
import tempfile
import time


SCHEMA = "lucidfence-trusted-supervisor-receipt/v2"
OBSERVATION_SCHEMA = "lucidfence-http-observation/v1"
SELF_DIGEST_ZERO = "0" * 64
MAX_HTTP_BODY = 64 * 1024
MAX_CHILD_FILE = 10 * 1024 * 1024
MAX_OBSERVATION = 1024 * 1024
SHA40 = re.compile(r"[0-9a-f]{40}")
SENSITIVE_PATTERNS = (
    re.compile(rb"ghp_[A-Za-z0-9]{20,}"),
    re.compile(rb"ghs_[A-Za-z0-9]{20,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(b"REAL_TENANT_" + b"PRIVATE_DATA"),
    re.compile(b"TENANT_SECRET_" + b"TEST_VALUE"),
)
COMMAND_IDS = {
    "reality": "blackbox-reality",
    "runtime": "blackbox-runtime",
}
OBSERVATION_TOTALS = {"reality": 7, "runtime": 2}
CONTEXT_KEYS = {
    "base_sha",
    "head_sha",
    "request_run_attempt",
    "request_run_id",
    "trusted_source_sha",
}


class _ServerNotReady(Exception):
    """The candidate has not begun accepting loopback HTTP connections."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_document(value: object) -> bytes:
    return _canonical_bytes(value) + b"\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _seal(receipt: dict[str, object]) -> str:
    digest = receipt.setdefault(
        "receipt_digest",
        {"algorithm": "sha256", "value": SELF_DIGEST_ZERO},
    )
    if not isinstance(digest, dict):
        raise RuntimeError("supervisor receipt digest field is invalid")
    digest["algorithm"] = "sha256"
    digest["value"] = SELF_DIGEST_ZERO
    value = hashlib.sha256(_canonical_bytes(receipt)).hexdigest()
    digest["value"] = value
    return value


def _validated_context(context: dict[str, object] | None) -> dict[str, object]:
    if not isinstance(context, dict) or set(context) != CONTEXT_KEYS:
        raise ValueError("supervisor context fields are not exact")
    values = dict(context)
    for key in ("base_sha", "head_sha", "trusted_source_sha"):
        if not isinstance(values[key], str) or not SHA40.fullmatch(values[key]):
            raise ValueError("supervisor commit identity is invalid")
    if values["trusted_source_sha"] != values["base_sha"]:
        raise ValueError("trusted supervisor source must be the pull request base")
    attempt = values["request_run_attempt"]
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("supervisor request run attempt is invalid")
    run_id = values["request_run_id"]
    if (
        not isinstance(run_id, str)
        or not run_id.isdigit()
        or int(run_id) < 1
        or len(run_id) > 32
    ):
        raise ValueError("supervisor request run ID is invalid")
    return values


def _validated_target(repo_root: Path) -> Path:
    candidate = repo_root / "saas_server.py"
    try:
        metadata = candidate.lstat()
    except OSError as exc:
        raise RuntimeError("candidate saas_server.py is missing") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError("candidate saas_server.py must be a regular non-symlink file")
    target = candidate.resolve(strict=True)
    if target.parent != repo_root:
        raise RuntimeError("candidate saas_server.py escapes the repository root")
    return target


def _observer_path() -> Path:
    logical = Path(__file__)
    if logical.is_symlink():
        raise RuntimeError("trusted supervisor executable must not be a symlink")
    observer = logical.resolve(strict=True)
    if not observer.is_file():
        raise RuntimeError("trusted supervisor executable is invalid")
    return observer


def _child_identity(untrusted_user: str | None) -> tuple[int | None, int | None]:
    if untrusted_user is None:
        raise RuntimeError("the supervisor must name an unprivileged child user")
    if os.geteuid() != 0:
        raise RuntimeError("dropping to the untrusted user requires a root supervisor")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", untrusted_user):
        raise RuntimeError("untrusted user name is invalid")
    account = pwd.getpwnam(untrusted_user)
    if account.pw_uid == 0 or account.pw_gid == 0:
        raise RuntimeError("candidate HTTP server user must be unprivileged")
    return account.pw_uid, account.pw_gid


def _allocate_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _reject_sensitive(raw: bytes, label: str) -> None:
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(raw):
            raise RuntimeError(f"{label} contains sensitive data")


def _validate_timestamp(value: object) -> None:
    if not isinstance(value, str):
        raise RuntimeError("candidate HTTP timestamp is missing")
    try:
        observed = calendar.timegm(time.strptime(value, "%Y-%m-%dT%H:%M:%SZ"))
    except (OverflowError, ValueError) as exc:
        raise RuntimeError("candidate HTTP timestamp is invalid") from exc
    delta = observed - time.time()
    if delta > 30 or delta < -300:
        raise RuntimeError("candidate HTTP timestamp is stale or in the future")


def _validate_health(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != {
        "desktop_nonce",
        "service",
        "status",
        "ts",
    }:
        raise RuntimeError("candidate health response fields are not exact")
    if (
        payload["desktop_nonce"] != ""
        or payload["service"] != "lucidfence"
        or payload["status"] != "ok"
    ):
        raise RuntimeError("candidate health response is not healthy")
    _validate_timestamp(payload["ts"])


def _validate_ready(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != {
        "cluster_mode",
        "leader",
        "ready",
        "service",
        "tenants_loaded",
        "ts",
    }:
        raise RuntimeError("candidate readiness response fields are not exact")
    tenants = payload["tenants_loaded"]
    if (
        payload["cluster_mode"] != "single"
        or payload["leader"] is not True
        or payload["ready"] is not True
        or payload["service"] != "lucidfence"
        or isinstance(tenants, bool)
        or not isinstance(tenants, int)
        or tenants < 0
    ):
        raise RuntimeError("candidate readiness response is not ready")
    _validate_timestamp(payload["ts"])


def _http_observation(port: int, path: str, timeout: float) -> dict[str, object]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        try:
            connection.request(
                "GET",
                path,
                headers={
                    "Accept": "application/json",
                    "Connection": "close",
                    "User-Agent": "lucidfence-trusted-supervisor",
                },
            )
            response = connection.getresponse()
        except (ConnectionError, OSError, TimeoutError, http.client.HTTPException) as exc:
            raise _ServerNotReady from exc
        raw = response.read(MAX_HTTP_BODY + 1)
        if len(raw) > MAX_HTTP_BODY or not raw:
            raise RuntimeError("candidate HTTP response is absent or too large")
        _reject_sensitive(raw, "candidate HTTP response")
        media_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
        if response.status != 200 or media_type != "application/json":
            raise RuntimeError("candidate HTTP response status or media type is invalid")
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("candidate HTTP response is not valid JSON") from exc
        if path == "/api/health":
            _validate_health(payload)
        elif path == "/api/readyz":
            _validate_ready(payload)
        else:
            raise RuntimeError("trusted HTTP observation path is invalid")
        return {
            "body_bytes": len(raw),
            "body_sha256": hashlib.sha256(raw).hexdigest(),
            "content_type": media_type,
            "method": "GET",
            "path": path,
            "status": response.status,
        }
    finally:
        connection.close()


def _observe_http_server(
    process: subprocess.Popen[bytes],
    port: int,
    kind: str,
    timeout_seconds: int,
) -> tuple[dict[str, int], bytes]:
    total = OBSERVATION_TOTALS[kind]
    deadline = time.monotonic() + timeout_seconds
    observations: list[dict[str, object]] = []
    while True:
        if process.poll() is not None:
            raise RuntimeError("candidate HTTP server exited before observation")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("candidate HTTP server did not become ready")
        try:
            observations.append(
                _http_observation(port, "/api/health", min(2.0, remaining))
            )
            break
        except _ServerNotReady:
            time.sleep(min(0.05, max(0.0, remaining)))

    for index in range(1, total):
        if process.poll() is not None:
            raise RuntimeError("candidate HTTP server exited during observation")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("candidate HTTP observation timed out")
        path = "/api/readyz" if index % 2 else "/api/health"
        try:
            observations.append(_http_observation(port, path, min(2.0, remaining)))
        except _ServerNotReady as exc:
            raise RuntimeError("candidate HTTP server stopped accepting requests") from exc

    if process.poll() is not None:
        raise RuntimeError("candidate HTTP server did not remain live")
    transcript = _canonical_document(
        {
            "kind": kind,
            "observations": observations,
            "schema": OBSERVATION_SCHEMA,
        }
    )
    if not 1 <= len(transcript) <= MAX_OBSERVATION:
        raise RuntimeError("trusted HTTP observation is outside the safety bound")
    _reject_sensitive(transcript, "trusted HTTP observation")
    return {"passed": total, "total": total}, transcript


def _stop_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=10)


def _write_receipt(path: Path, receipt: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.exists():
        raise RuntimeError("supervisor receipt path must not already exist")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        payload = _canonical_document(receipt)
        written = 0
        while written < len(payload):
            count = os.write(descriptor, payload[written:])
            if count <= 0:
                raise RuntimeError("supervisor receipt write was truncated")
            written += count
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o644)
    finally:
        os.close(descriptor)


def run_supervised_check(
    kind: str,
    repo_root: Path,
    candidate_python: Path,
    output_path: Path,
    *,
    timeout_seconds: int = 1800,
    untrusted_user: str | None = None,
    sandbox_dir: Path | None = None,
    playwright_browsers_path: Path | None = None,
    context: dict[str, object] | None = None,
) -> dict[str, object]:
    """Observe one candidate server and atomically write a parent-owned receipt."""
    del playwright_browsers_path
    if kind not in COMMAND_IDS:
        raise ValueError("unknown supervised evidence kind")
    if timeout_seconds < 1 or timeout_seconds > 3600:
        raise ValueError("supervised timeout is outside the safety bound")
    bound_context = _validated_context(context)
    repo_root = repo_root.resolve(strict=True)
    target = _validated_target(repo_root)
    observer = _observer_path()
    initial_target_digest = _sha256(target)
    candidate_python = Path(os.path.abspath(candidate_python))
    if (
        not candidate_python.exists()
        or candidate_python.is_dir()
        or not os.access(candidate_python, os.X_OK)
    ):
        raise RuntimeError("candidate Python interpreter is invalid")
    uid, gid = _child_identity(untrusted_user)

    runtime_root = Path(tempfile.mkdtemp(prefix="lf-supervisor-"))
    candidate_sandbox = (
        Path(os.path.abspath(sandbox_dir))
        if sandbox_dir is not None
        else runtime_root / "sandbox"
    )
    if candidate_sandbox.exists() or candidate_sandbox.is_symlink():
        shutil.rmtree(runtime_root, ignore_errors=True)
        raise RuntimeError("candidate sandbox path must not already exist")
    candidate_sandbox.mkdir(parents=True, mode=0o700)
    data_dir = candidate_sandbox / "data"
    temp_dir = candidate_sandbox / "tmp"
    data_dir.mkdir(mode=0o700)
    temp_dir.mkdir(mode=0o700)
    if uid is not None and gid is not None:
        for directory in (candidate_sandbox, data_dir, temp_dir):
            os.chown(directory, uid, gid)
            directory.chmod(0o700)

    port = _allocate_loopback_port()

    def child_setup() -> None:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_CHILD_FILE, MAX_CHILD_FILE))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        os.umask(0o077)
        if uid is not None and gid is not None:
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)

    environment = {
        "CI": "1",
        "HOME": str(candidate_sandbox),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "LUCIDFENCE_CONFIG_FILE": str(repo_root / "config.json"),
        "LUCIDFENCE_DATA_DIR": str(data_dir),
        "LUCIDFENCE_HOST": "127.0.0.1",
        "LUCIDFENCE_PORT": str(port),
        "LUCIDFENCE_WORKERS": "1",
        "NO_PROXY": "127.0.0.1,localhost",
        "PATH": f"{candidate_python.parent}:/usr/local/bin:/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHOME": "",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": "",
        "PYTHONSAFEPATH": "1",
        "TMPDIR": str(temp_dir),
        "TZ": "UTC",
        "no_proxy": "127.0.0.1,localhost",
    }
    command = [str(candidate_python), "-I", str(target)]
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=repo_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            preexec_fn=child_setup,
            start_new_session=True,
        )
        result, transcript = _observe_http_server(process, port, kind, timeout_seconds)
        _stop_process_group(process)
        if _sha256(target) != initial_target_digest:
            raise RuntimeError("candidate saas_server.py changed during observation")
        receipt: dict[str, object] = {
            "command_id": COMMAND_IDS[kind],
            "context": bound_context,
            "kind": kind,
            "observation": {
                "bytes": len(transcript),
                "sha256": hashlib.sha256(transcript).hexdigest(),
            },
            "observer": {
                "path": "scripts/supervise_autonomy_check.py",
                "sha256": _sha256(observer),
            },
            "result": result,
            "schema": SCHEMA,
            "status": "pass",
            "target": {
                "path": "saas_server.py",
                "sha256": initial_target_digest,
            },
        }
        _seal(receipt)
        _write_receipt(output_path, receipt)
        return receipt
    finally:
        if process is not None:
            _stop_process_group(process)
        shutil.rmtree(runtime_root, ignore_errors=True)
        if sandbox_dir is not None:
            shutil.rmtree(candidate_sandbox, ignore_errors=True)


def _context_from_args(args: argparse.Namespace) -> dict[str, object]:
    try:
        attempt = int(args.request_run_attempt)
    except (TypeError, ValueError) as exc:
        raise ValueError("supervisor request run attempt is invalid") from exc
    return _validated_context(
        {
            "base_sha": args.base_sha,
            "head_sha": args.head_sha,
            "request_run_attempt": attempt,
            "request_run_id": args.request_run_id,
            "trusted_source_sha": args.trusted_source_sha,
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=tuple(COMMAND_IDS), required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--candidate-python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sandbox-dir", type=Path)
    parser.add_argument("--playwright-browsers-path", type=Path)
    parser.add_argument("--untrusted-user")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--request-run-attempt", required=True)
    parser.add_argument("--request-run-id", required=True)
    parser.add_argument("--trusted-source-sha", required=True)
    args = parser.parse_args(argv)
    receipt = run_supervised_check(
        args.kind,
        args.repo_root,
        args.candidate_python,
        args.output,
        timeout_seconds=args.timeout_seconds,
        untrusted_user=args.untrusted_user,
        sandbox_dir=args.sandbox_dir,
        playwright_browsers_path=args.playwright_browsers_path,
        context=_context_from_args(args),
    )
    print(f"trusted-supervisor-receipt sha256={receipt['receipt_digest']['value']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
