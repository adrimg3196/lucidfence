#!/usr/bin/env python3
"""Local authentication, sessions and RBAC for the LucidFence SaaS.

100% local, no external identity provider:
- Passwords hashed with scrypt (salt + n + r + p), stored per-user as JSON.
- Sessions are random tokens stored server-side with expiry, returned to the
  client as an httpOnly cookie by the HTTP layer.
- RBAC: each user has a role per organization. Capability checks enforce what
  the UI/API can do (inspired by Fleet's capability-based authz model).

Roles:
  owner     -> full control of the org, billing, users, settings
  admin     -> manage devices/fences/actions/policies, not billing
  operator  -> run cycles, trigger actions, view everything
  viewer    -> read-only dashboards and reports
  auditor   -> immutable audit/compliance visibility + report export
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional


# Capability matrix per role. A capability is a coarse permission string.
ROLE_CAPS = {
    "owner": {
        "org:read", "org:update", "org:billing", "org:delete",
        "user:invite", "user:remove", "user:role",
        "device:read", "device:write", "device:action",
        "fence:read", "fence:write", "fence:delete",
        "engine:run", "engine:config", "policy:read", "policy:write",
        "route:read", "route:write", "route:delete",
        "workflow:read", "workflow:write",
        "incident:read", "incident:write",
        "report:read", "report:export",
        "company:read", "company:write", "company:run", "company:approve",
    },
    "admin": {
        "org:read", "org:update",
        "user:invite", "user:remove",
        "device:read", "device:write", "device:action",
        "fence:read", "fence:write", "fence:delete",
        "engine:run", "engine:config", "policy:read", "policy:write",
        "route:read", "route:write", "route:delete",
        "workflow:read", "workflow:write",
        "incident:read", "incident:write",
        "report:read", "report:export",
        "company:read", "company:write", "company:run", "company:approve",
    },
    "operator": {
        "org:read",
        "device:read", "device:action",
        "fence:read", "fence:write",
        "engine:run", "policy:read",
        "route:read", "route:write",
        "workflow:read", "workflow:write",
        "incident:read", "incident:write",
        "report:read", "company:read", "company:run",
    },
    "viewer": {
        "org:read", "device:read", "fence:read", "policy:read",
        "route:read", "workflow:read", "incident:read", "report:read", "company:read",
    },
    "auditor": {
        "org:read", "device:read", "fence:read", "policy:read",
        "route:read", "workflow:read", "incident:read", "report:read",
        "report:export", "audit:read", "company:read",
    },
}

ROLE_LABELS = {
    "owner": "Propietario",
    "admin": "Administrador",
    "operator": "Operador",
    "viewer": "Solo lectura",
    "auditor": "Auditor",
}

SESSION_TTL = 60 * 60 * 24 * 7  # 7 days


@dataclass
class User:
    id: str
    email: str
    name: str
    pw_hash: str
    pw_salt: str
    org_roles: dict = field(default_factory=dict)  # org_id -> role
    created_at: str = ""
    active: bool = True
    external_identities: list[dict] = field(default_factory=list)

    def to_public(self) -> dict:
        return {
            "id": self.id, "email": self.email, "name": self.name,
            "org_roles": self.org_roles, "created_at": self.created_at,
            "active": self.active,
        }

    def role_for(self, org_id: str) -> Optional[str]:
        return self.org_roles.get(org_id)


def _hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if salt is None:
        salt = os.urandom(16).hex()
    # stdlib PBKDF2-HMAC-SHA256 (100k rounds). Standard, audited KDF.
    # (Replaces a hand-rolled HMAC loop — same on-disk format: pw_hash.hex+pw_salt.)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                bytes.fromhex(salt), 100000, 64)
    return dk.hex(), salt


def verify_password(password: str, pw_hash: str, pw_salt: str) -> bool:
    dk, _ = _hash_password(password, pw_salt)
    return hmac.compare_digest(dk, pw_hash)


class AuthStore:
    def __init__(self, root: Path, *, session_ttl: int = SESSION_TTL,
                 session_idle_timeout: int = 60 * 60 * 8):
        self.root = Path(root)
        self.users_path = self.root / "_users.json"
        self.sessions_path = self.root / "_sessions.json"
        self._users: dict[str, User] = {}
        self._by_email: dict[str, str] = {}
        self._by_external_identity: dict[tuple[str, str], str] = {}
        self._sessions: dict[str, dict] = {}
        self._lock = threading.RLock()
        self.session_ttl = int(session_ttl)
        self.session_idle_timeout = int(session_idle_timeout)
        if self.session_ttl <= 0 or self.session_idle_timeout <= 0:
            raise ValueError("session timeouts must be positive")
        self._load()

    # ---- persistence ----------------------------------------------------
    def _load(self):
        if self.users_path.exists():
            try:
                raw = json.loads(self.users_path.read_text(encoding="utf-8"))
                for u in raw:
                    user = User(**u)
                    self._users[user.id] = user
                    self._by_email[user.email.lower()] = user.id
                    for identity in user.external_identities:
                        issuer = str(identity.get("issuer") or "")
                        subject = str(identity.get("subject") or "")
                        key = (issuer, subject)
                        if not issuer or not subject or key in self._by_external_identity:
                            raise ValueError("invalid external identity index")
                        self._by_external_identity[key] = user.id
            except Exception:
                self._users = {}
                self._by_email = {}
                self._by_external_identity = {}
        if self.sessions_path.exists():
            try:
                self._sessions = json.loads(self.sessions_path.read_text(encoding="utf-8"))
            except Exception:
                self._sessions = {}

    @staticmethod
    def _atomic_json(path: Path, value: Any):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
            os.chmod(path, 0o600)
            dir_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass

    def _save_users(self):
        with self._lock:
            self._atomic_json(self.users_path, [asdict(u) for u in self._users.values()])

    def _save_sessions(self):
        with self._lock:
            self._atomic_json(self.sessions_path, self._sessions)

    # ---- user management ----------------------------------------------
    def create_user(self, email: str, name: str, password: str,
                    org_id: str, role: str = "owner") -> User:
        with self._lock:
            email = email.lower().strip()
            if email in self._by_email:
                raise ValueError("El email ya está registrado")
            if role not in ROLE_CAPS:
                raise ValueError(f"Rol inválido: {role}")
            pw_hash, salt = _hash_password(password)
            user = User(
                id=f"usr_{uuid.uuid4().hex[:10]}",
                email=email, name=name, pw_hash=pw_hash, pw_salt=salt,
                org_roles={org_id: role}, created_at=_now(),
            )
            self._users[user.id] = user
            self._by_email[email] = user.id
            self._save_users()
            return user

    def get(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        return self._users.get(self._by_email.get(email.lower().strip()))

    def get_by_external_identity(self, issuer: str, subject: str) -> Optional[User]:
        with self._lock:
            return self._users.get(self._by_external_identity.get((issuer, subject)))

    def link_external_identity(self, user_id: str, issuer: str, subject: str) -> User:
        """Explicit link primitive. HTTP callers must enforce CSRF + recent reauth."""
        with self._lock:
            user = self._users.get(user_id)
            if not user or not issuer or not subject:
                raise ValueError("invalid_external_identity")
            owner = self._by_external_identity.get((issuer, subject))
            if owner and owner != user_id:
                raise ValueError("external_identity_conflict")
            if not owner:
                user.external_identities.append({"issuer": issuer, "subject": subject})
                self._by_external_identity[(issuer, subject)] = user_id
                self._save_users()
            return user

    def complete_oidc_login(self, issuer: str, subject: str, email: str, name: str,
                            org_id: str, role: str, *, old_session: str = "") -> tuple[User, str]:
        """Atomically find/provision an external identity and rotate the session.

        Provisioning policy (verified email/domain/invitation/bootstrap) is decided
        by the OIDC HTTP layer before this mutation. Email is never used to link.
        """
        with self._lock:
            user = self.get_by_external_identity(issuer, subject)
            if user is None:
                if role not in ROLE_CAPS or not org_id:
                    raise ValueError("provisioning_denied")
                canonical = email.strip().lower()
                # Never merge with an existing password or different-issuer user.
                storage_email = canonical
                if storage_email in self._by_email:
                    storage_email = f"oidc-{uuid.uuid4().hex[:12]}@external.invalid"
                user = User(id=f"usr_{uuid.uuid4().hex[:10]}", email=storage_email,
                            name=name or canonical, pw_hash="", pw_salt="",
                            org_roles={org_id: role}, created_at=_now(),
                            external_identities=[{"issuer": issuer, "subject": subject,
                                                  "email": canonical}])
                self._users[user.id] = user
                self._by_email[storage_email] = user.id
                self._by_external_identity[(issuer, subject)] = user.id
                self._save_users()
            if not user.active:
                raise ValueError("account_inactive")
            if old_session:
                self._sessions.pop(old_session, None)
            token = self._create_session_locked(user.id)
            self._save_sessions()
            return user, token

    def authenticate(self, email: str, password: str) -> Optional[User]:
        u = self.get_by_email(email)
        if not u or not u.active:
            return None
        if verify_password(password, u.pw_hash, u.pw_salt):
            return u
        return None

    def add_org_role(self, user_id: str, org_id: str, role: str) -> bool:
        u = self._users.get(user_id)
        if not u:
            return False
        u.org_roles[org_id] = role
        self._save_users()
        return True

    # ---- sessions -------------------------------------------------------
    def _create_session_locked(self, user_id: str) -> str:
        token = os.urandom(32).hex()
        now = time.time()
        self._sessions[token] = {
            "user_id": user_id,
            "created_at": _now(),
            "issued_at": now,
            "last_seen_at": now,
            "expires_at": now + self.session_ttl,
        }
        return token

    def create_session(self, user_id: str) -> str:
        with self._lock:
            token = self._create_session_locked(user_id)
            self._save_sessions()
            return token

    def get_session(self, token: str) -> Optional[dict]:
        with self._lock:
            s = self._sessions.get(token)
            if not s:
                return None
            now = time.time()
            last_seen = float(s.get("last_seen_at", s.get("issued_at", now)))
            if s.get("expires_at", 0) < now or last_seen + self.session_idle_timeout < now:
                self._sessions.pop(token, None)
                self._save_sessions()
                return None
            s["last_seen_at"] = now
            self._save_sessions()
            return dict(s)

    def destroy_session(self, token: str):
        with self._lock:
            self._sessions.pop(token, None)
            self._save_sessions()

    # ---- RBAC -----------------------------------------------------------
    @staticmethod
    def can(role: Optional[str], capability: str) -> bool:
        if not role:
            return False
        return capability in ROLE_CAPS.get(role, set())


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
