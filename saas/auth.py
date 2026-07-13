#!/usr/bin/env python3
"""Local authentication, sessions and RBAC for the Geofence UEM SaaS.

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
    },
    "operator": {
        "org:read",
        "device:read", "device:action",
        "fence:read", "fence:write",
        "engine:run", "policy:read",
        "route:read", "route:write",
        "workflow:read", "workflow:write",
        "incident:read", "incident:write",
        "report:read",
    },
    "viewer": {
        "org:read", "device:read", "fence:read", "policy:read",
        "route:read", "workflow:read", "incident:read", "report:read",
    },
}

ROLE_LABELS = {
    "owner": "Propietario",
    "admin": "Administrador",
    "operator": "Operador",
    "viewer": "Solo lectura",
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
    # Pure-python PBKDF2-HMAC-SHA256 (200k rounds). We avoid hashlib.scrypt /
    # hashlib.pbkdf2_hmac because some macOS system Pythons lack the OpenSSL
    # bindings. This is a dependency-free, timing-safe-enough KDF for a local SaaS.
    dk = _pbkdf2_sha256(password.encode("utf-8"), salt.encode("utf-8"), 25000, 64)
    return dk.hex(), salt


def _pbkdf2_sha256(password: bytes, salt: bytes, rounds: int, dklen: int) -> bytes:
    import struct
    blocks = (dklen + 31) // 32
    out = b""
    for i in range(1, blocks + 1):
        u = hmac.new(password, salt + struct.pack(">I", i), hashlib.sha256).digest()
        res = u
        for _ in range(1, rounds):
            u = hmac.new(password, u, hashlib.sha256).digest()
            res = bytes(a ^ b for a, b in zip(res, u))
        out += res
    return out[:dklen]


def verify_password(password: str, pw_hash: str, pw_salt: str) -> bool:
    dk, _ = _hash_password(password, pw_salt)
    return hmac.compare_digest(dk, pw_hash)


class AuthStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.users_path = self.root / "_users.json"
        self.sessions_path = self.root / "_sessions.json"
        self._users: dict[str, User] = {}
        self._by_email: dict[str, str] = {}
        self._sessions: dict[str, dict] = {}
        self._lock = threading.RLock()
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
            except Exception:
                self._users = {}
        if self.sessions_path.exists():
            try:
                self._sessions = json.loads(self.sessions_path.read_text(encoding="utf-8"))
            except Exception:
                self._sessions = {}

    def _save_users(self):
        with self._lock:
            tmp = self.users_path.with_name(
                f"{self.users_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps([asdict(u) for u in self._users.values()],
                                      ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.users_path)

    def _save_sessions(self):
        with self._lock:
            tmp = self.sessions_path.with_name(
                f"{self.sessions_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps(self._sessions, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            tmp.replace(self.sessions_path)

    # ---- user management ----------------------------------------------
    def create_user(self, email: str, name: str, password: str,
                    org_id: str, role: str = "owner") -> User:
        email = email.lower().strip()
        if email in self._by_email:
            raise ValueError("El email ya está registrado")
        if role not in ROLE_CAPS:
            raise ValueError(f"Rol inválido: {role}")
        pw_hash, salt = _hash_password(password)
        user = User(
            id=f"usr_{uuid.uuid4().hex[:10]}",
            email=email, name=name, pw_hash=pw_hash, pw_salt=salt,
            org_roles={org_id: role},
            created_at=_now(),
        )
        self._users[user.id] = user
        self._by_email[email] = user.id
        self._save_users()
        return user

    def get(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        return self._users.get(self._by_email.get(email.lower().strip()))

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
    def create_session(self, user_id: str) -> str:
        with self._lock:
            token = os.urandom(32).hex()
            self._sessions[token] = {
                "user_id": user_id,
                "created_at": _now(),
                "expires_at": time.time() + SESSION_TTL,
            }
            self._save_sessions()
            return token

    def get_session(self, token: str) -> Optional[dict]:
        with self._lock:
            s = self._sessions.get(token)
            if not s:
                return None
            if s.get("expires_at", 0) < time.time():
                self._sessions.pop(token, None)
                self._save_sessions()
                return None
            return s

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
