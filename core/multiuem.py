"""Normalized domain models shared by tenant-local Multi-UEM providers."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypeGuard


_UNUSABLE_IDENTITIES = {"NA", "NONE", "NULL", "UNKNOWN", "UNAVAILABLE", "0"}


def normalize_identity(value: object | None) -> str | None:
    """Return a correlation-safe identity, or ``None`` for empty placeholders."""
    if value is None:
        return None
    normalized = "".join(character for character in str(value) if character.isalnum()).upper()
    if not normalized or normalized in _UNUSABLE_IDENTITIES:
        return None
    return normalized


@dataclass(frozen=True)
class ProviderCapabilities:
    inventory: bool = True
    location: bool = False
    native_geofences: bool = False
    actions: frozenset[str] = frozenset()


@dataclass(frozen=True)
class LocationEvidence:
    lat: float
    lng: float
    observed_at: str | None
    accuracy_m: float | None
    provider: str
    source: str

    def quality(
        self,
        now: datetime,
        max_age_seconds: int,
        max_accuracy_m: float,
        future_tolerance_seconds: int = 60,
    ) -> tuple[bool, str]:
        """Classify whether this observation is safe to use for geofencing."""
        if not self._valid_coordinate(self.lat, -90, 90) or not self._valid_coordinate(
            self.lng, -180, 180
        ):
            return False, "invalid_coordinates"

        if not isinstance(self.observed_at, str):
            return False, "invalid_timestamp"
        try:
            observed_at = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
            if observed_at.tzinfo is None or now.tzinfo is None:
                return False, "invalid_timestamp"
            age_seconds = (now - observed_at).total_seconds()
        except (AttributeError, TypeError, ValueError, OverflowError):
            return False, "invalid_timestamp"

        if age_seconds < -future_tolerance_seconds:
            return False, "future"
        if age_seconds > max_age_seconds:
            return False, "stale"

        if self.accuracy_m is not None:
            if not self._valid_number(self.accuracy_m) or self.accuracy_m < 0:
                return False, "invalid_accuracy"
            if self.accuracy_m > max_accuracy_m:
                return False, "inaccurate"

        return True, "accepted"

    @staticmethod
    def _valid_number(value: object) -> TypeGuard[int | float]:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    @classmethod
    def _valid_coordinate(cls, value: object, minimum: float, maximum: float) -> bool:
        return cls._valid_number(value) and minimum <= value <= maximum


@dataclass
class NormalizedDevice:
    canonical_id: str
    provider: str
    provider_device_id: str
    name: str
    platform: str
    serial_number: str | None = None
    imei: str | None = None
    compliant: bool | None = None
    status: str = "unknown"
    location: LocationEvidence | None = None
    inventory: dict = field(default_factory=dict)
    provider_refs: dict[str, str] = field(default_factory=dict)
    provenance: dict[str, str] = field(default_factory=dict)
    identity_conflict: bool = False


@dataclass(frozen=True)
class ProviderHealth:
    status: str
    devices: int = 0
    detail: str | None = None


@dataclass
class SyncResult:
    devices: list[NormalizedDevice] = field(default_factory=list)
    health: dict[str, ProviderHealth] = field(default_factory=dict)
    status: str = "ok"
