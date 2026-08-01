"""Tenant-scoped API keys and tamper-evident local audit log."""
from __future__ import annotations

import hashlib
import hmac
import base64
import json
import os
import threading
import time
from pathlib import Path

_AUDIT_LOCK = threading.RLock()


class APIKeyStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.path = self.root / "_api_keys.json"
        self._lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def _load(self) -> list[dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, records: list[dict]) -> None:
        temp = self.path.with_suffix(f".tmp-{os.getpid()}-{threading.get_ident()}")
        temp.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, self.path)
        os.chmod(self.path, 0o600)

    def create(self, org_id: str, name: str, role: str = "operator") -> tuple[str, dict]:
        if role not in {"operator", "viewer"}:
            raise ValueError("API key role must be operator or viewer")
        clean_name = str(name or "automation").strip()[:80]
        if not org_id or not clean_name:
            raise ValueError("org_id and name are required")
        token = "lf_" + base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        record = {"id": os.urandom(8).hex(), "org_id": org_id, "name": clean_name,
                  "role": role, "prefix": token[:11], "hash": self._digest(token),
                  "created_at": now, "last_used_at": None, "revoked_at": None}
        with self._lock:
            records = self._load()
            records.append(record)
            self._save(records)
        return token, self._public(record)

    def authenticate(self, token: str) -> dict | None:
        if not token.startswith("lf_") or len(token) < 35:
            return None
        digest = self._digest(token)
        with self._lock:
            records = self._load()
            found = None
            for record in records:
                if not record.get("revoked_at") and hmac.compare_digest(str(record.get("hash") or ""), digest):
                    record["last_used_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    found = dict(record)
                    break
            if found:
                self._save(records)
                return self._public(found)
        return None

    def list_for_org(self, org_id: str) -> list[dict]:
        with self._lock:
            return [self._public(record) for record in self._load() if record.get("org_id") == org_id]

    def revoke(self, org_id: str, key_id: str) -> bool:
        changed = False
        with self._lock:
            records = self._load()
            for record in records:
                if record.get("org_id") == org_id and record.get("id") == key_id and not record.get("revoked_at"):
                    record["revoked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    changed = True
            if changed:
                self._save(records)
        return changed

    @staticmethod
    def _public(record: dict) -> dict:
        return {key: record.get(key) for key in ("id", "org_id", "name", "role", "prefix", "created_at", "last_used_at", "revoked_at")}


def append_audit(root: str | Path, event: dict) -> dict:
    """Append a hash-chained JSON event suitable for local SIEM export."""
    directory = Path(root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "audit.jsonl"
    with _AUDIT_LOCK:
        previous_hash = "0" * 64
        try:
            last = path.read_text(encoding="utf-8").splitlines()[-1]
            previous_hash = str(json.loads(last).get("hash") or previous_hash)
        except (OSError, IndexError, json.JSONDecodeError):
            pass
        body = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **event,
                "previous_hash": previous_hash}
        canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        body["hash"] = hashlib.sha256(canonical.encode()).hexdigest()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "\n")
        os.chmod(path, 0o600)
    return body


def verify_audit(root: str | Path) -> dict:
    path = Path(root) / "audit.jsonl"
    previous = "0" * 64
    count = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {"ok": True, "events": 0}
    for line in lines:
        try:
            item = json.loads(line)
            digest = item.pop("hash")
            if item.get("previous_hash") != previous:
                return {"ok": False, "events": count, "error": "chain_mismatch"}
            canonical = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if not hmac.compare_digest(digest, hashlib.sha256(canonical.encode()).hexdigest()):
                return {"ok": False, "events": count, "error": "hash_mismatch"}
            previous = digest
            count += 1
        except (json.JSONDecodeError, KeyError, TypeError):
            return {"ok": False, "events": count, "error": "invalid_event"}
    return {"ok": True, "events": count, "head": previous}
