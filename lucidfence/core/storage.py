"""Free blob storage for LucidFence report attachments.

LucidFence emits PDF/CSV reports (incident exports, audit bundles).
Where do those blobs live without a paid S3? Two free options, both
gated behind the same tiny interface so the caller doesn't care:

  1. LOCAL VOLUME (default) — on Fly.io the container has a persistent
     volume mounted at /app/data; on your Mac it's just data/reports/.
     $0, always available, no credentials. This is the default.

  2. CLOUDFLARE R2 (optional, 10GB free tier) — only if the operator
     mounts R2 credentials via Fly secrets / env vars. Off by default.
     We talk to R2's S3-compatible API with plain `requests` + SigV4
     (no boto). If creds are absent we silently fall back to local.

Security:
  - Never raises: a storage failure returns False and the caller keeps the
    local copy (or skips the attachment).
  - R2 creds come ONLY from env (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY, R2_BUCKET). We never log them.
"""
from __future__ import annotations

import os
from typing import Optional

LOCAL_DIR = "data/reports"
# S3-compatible R2 endpoint (S3 API, not the admin API).
R2_ENDPOINT_TMPL = "https://{account_id}.r2.cloudflarestorage.com"


def _local_path(key: str) -> str:
    os.makedirs(LOCAL_DIR, exist_ok=True)
    # Defang path traversal: keep only the basename.
    safe = os.path.basename(key.replace("\\", "/"))
    return os.path.join(LOCAL_DIR, safe)


def save_local(key: str, data: bytes) -> bool:
    try:
        path = _local_path(key)
        with open(path, "wb") as f:
            f.write(data)
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass
        return True
    except Exception:
        return False


def load_local(key: str) -> Optional[bytes]:
    try:
        with open(_local_path(key), "rb") as f:
            return f.read()
    except Exception:
        return None


def _r2_configured() -> bool:
    return bool(
        os.environ.get("R2_ACCOUNT_ID") and os.environ.get("R2_ACCESS_KEY_ID")
        and os.environ.get("R2_SECRET_ACCESS_KEY") and os.environ.get("R2_BUCKET")
    )


def save(key: str, data: bytes, *, prefer_r2: bool = True) -> str:
    """Store a blob. Returns 'local' | 'r2' | 'failed'.

    Never raises. Caller can ignore the result; a failed upload just means
    the report wasn't persisted remotely (local copy may still exist).
    """
    if prefer_r2 and _r2_configured():
        try:
            _save_r2(key, data)
            return "r2"
        except Exception:
            pass  # fall through to local
    if save_local(key, data):
        return "local"
    return "failed"


def _save_r2(key: str, data: bytes) -> None:
    """Put an object to R2 via S3-compatible API (SigV4, no boto).

    Raises on any failure; caller decides fallback.
    """
    import datetime
    import hashlib
    import hmac

    import requests

    account = os.environ["R2_ACCOUNT_ID"]
    ak = os.environ["R2_ACCESS_KEY_ID"]
    sk = os.environ["R2_SECRET_ACCESS_KEY"]
    bucket = os.environ["R2_BUCKET"]
    endpoint = R2_ENDPOINT_TMPL.format(account_id=account)
    url = f"{endpoint}/{bucket}/{key}"
    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    # SigV4 (simplified S3 auth: unsigned payload sha256).
    payload_hash = hashlib.sha256(data).hexdigest()
    headers = {
        "Host": f"{account}.r2.cloudflarestorage.com",
        "X-Amz-Date": amz_date,
        "X-Amz-Content-Sha256": payload_hash,
    }
    # Build canonical request + string-to-sign (SigV4).
    canonical = (
        "PUT\n/{bucket}/{key}\n\n"
        "host:{host}\nx-amz-content-sha256:{ph}\n"
        "x-amz-date:{ad}\n\n"
        "host;x-amz-content-sha256;x-amz-date\n{ph}"
    ).format(bucket=bucket, key=key, host=headers["Host"],
               ph=payload_hash, ad=amz_date)
    scope = f"{date_stamp}/auto/s3/aws4_request"
    string_to_sign = (
        "AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n"
        + hashlib.sha256(canonical.encode()).hexdigest()
    )
    def _sig(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()
    k_date = _sig(("AWS4" + sk).encode(), date_stamp)
    k_region = _sig(k_date, "auto")
    k_service = _sig(k_region, "s3")
    k_signing = _sig(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    auth = (
        f"AWS4-HMAC-SHA256 Credential={ak}/{scope}, "
        f"SignedHeaders=host;x-amz-content-sha256;x-amz-date, "
        f"Signature={signature}"
    )
    headers["Authorization"] = auth
    headers["Content-Type"] = "application/octet-stream"
    r = requests.put(url, data=data, headers=headers, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(f"R2 put failed: {r.status_code} {r.text[:120]}")


def available_backends() -> list:
    backs = ["local"]
    if _r2_configured():
        backs.append("r2")
    return backs
