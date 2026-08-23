"""Server-issued nonce cache with single-use, TTL, LRU, and replay detection.

A nonce proves the attestation blob was produced *in response to* a challenge we
just issued (anti-replay). The nonce is CSPRNG >= 128-bit, bound to a single
device, expires after ``ttl_seconds`` (default 60), and is consumed exactly
once: a second presentation of the same nonce is a replay and is rejected.

Thread-safe (guarded by ``_lock``) because the Risk Engine and the API surface
may issue/verify concurrently.
"""
from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable, Optional

DEFAULT_TTL_SECONDS = 60
DEFAULT_MAX_ENTRIES = 4096
_NONCE_BYTES = 16  # 128-bit


@dataclass
class _Entry:
    device_id: Optional[str]
    issued_at: float
    consumed: bool = False


class NonceCache:
    """LRU + TTL + single-use nonce store with replay detection.

    ``clock`` is injectable so tests can advance time deterministically without
    real wall-clock sleeps (the repo test runner has no pytest fixtures).
    """

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._store: "OrderedDict[str, _Entry]" = OrderedDict()

    @staticmethod
    def _new_nonce() -> str:
        # 128-bit CSPRNG, hex-encoded (32 chars).
        return secrets.token_hex(_NONCE_BYTES)

    def issue(self, device_id: Optional[str] = None) -> str:
        """Issue a fresh single-use nonce (>=128-bit) and store it pending."""
        with self._lock:
            nonce = self._new_nonce()
            while nonce in self._store:
                nonce = self._new_nonce()
            self._store[nonce] = _Entry(
                device_id=device_id, issued_at=self._clock(), consumed=False)
            self._evict_locked()
            return nonce

    def _evict_locked(self) -> None:
        # Drop expired entries and trim LRU beyond max_entries.
        now = self._clock()
        expired = [n for n, e in self._store.items()
                   if now - e.issued_at > self.ttl]
        for n in expired:
            self._store.pop(n, None)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def consume(self, nonce: str, device_id: Optional[str] = None) -> tuple[bool, str]:
        """Consume ``nonce``. Returns ``(ok, reason)``.

        Reasons:
          ``ok``            -> nonce valid, single-use, fresh, device matches
          ``not_found``     -> unknown / already expired nonce  -> treat as UNKNOWN
          ``replay``        -> already consumed once           -> REJECTED
          ``expired``       -> age > ttl                        -> UNKNOWN (stale)
          ``device_mismatch``-> bound device differs           -> UNVERIFIED
        """
        with self._lock:
            entry = self._store.get(nonce)
            if entry is None:
                return False, "not_found"
            # Expiry must be checked BEFORE the consumed flag: a nonce that has
            # expired is reported as "expired" (-> UNKNOWN), not "replay".
            age = self._clock() - entry.issued_at
            if age > self.ttl:
                self._store.pop(nonce, None)
                return False, "expired"
            if entry.consumed:
                # Already used: classic replay / double-submission.
                return False, "replay"
            if device_id is not None and entry.device_id is not None \
                    and entry.device_id != device_id:
                return False, "device_mismatch"
            entry.consumed = True
            self._store.move_to_end(nonce)
            return True, "ok"
