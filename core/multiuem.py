"""Normalized domain models shared by tenant-local Multi-UEM providers."""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, TypeGuard


_UNUSABLE_IDENTITIES = {"NA", "NONE", "NULL", "UNKNOWN", "UNAVAILABLE", "0"}


def normalize_identity(value: object | None) -> str | None:
    """Return a correlation-safe identity, or ``None`` for empty placeholders."""
    if value is None:
        return None
    text = str(value)
    if not text.isascii():
        return None
    normalized = "".join(character for character in text if character.isalnum()).upper()
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
        max_age_seconds: int | float,
        max_accuracy_m: float,
        future_tolerance_seconds: int | float = 60,
    ) -> tuple[bool, str]:
        """Classify whether this observation is safe to use for geofencing."""
        limits = (max_age_seconds, max_accuracy_m, future_tolerance_seconds)
        if any(not self._valid_number(limit) or limit < 0 for limit in limits):
            return False, "invalid_limits"

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


@dataclass(frozen=True)
class ProviderBinding:
    name: str
    capabilities: ProviderCapabilities
    fetch_devices: Callable[[], list[NormalizedDevice]]
    execute_action: Callable[[str, str, dict, bool], dict] | None = None


class MultiUEMOrchestrator:
    """Isolate provider failures and conservatively consolidate their inventory."""

    def __init__(
        self,
        bindings: list[ProviderBinding],
        max_location_age_seconds: int | float = 900,
        max_accuracy_m: float = 500,
    ) -> None:
        self._bindings = {binding.name: binding for binding in bindings}
        self.max_location_age_seconds = max_location_age_seconds
        self.max_accuracy_m = max_accuracy_m
        self._health: dict[str, ProviderHealth] = {}

    def sync(self, now: datetime | None = None) -> SyncResult:
        now = now or datetime.now(timezone.utc)
        records: list[NormalizedDevice] = []
        health: dict[str, ProviderHealth] = {}

        for name, binding in sorted(self._bindings.items()):
            try:
                fetched = binding.fetch_devices()
                provider_records = [deepcopy(item) for item in fetched]
                for item in provider_records:
                    item.provider = name
                    item.provider_refs = {name: item.provider_device_id}
                records.extend(provider_records)
                health[name] = ProviderHealth("ok", len(provider_records))
            except Exception as exc:
                health[name] = ProviderHealth("error", detail=type(exc).__name__)

        devices = self._consolidate(records, now)
        successes = sum(item.status == "ok" for item in health.values())
        if health and successes == 0:
            status = "error"
        elif successes < len(health):
            status = "degraded"
        else:
            status = "ok"
        self._health = health
        return SyncResult(devices=devices, health=health, status=status)

    def _consolidate(
        self, records: list[NormalizedDevice], now: datetime
    ) -> list[NormalizedDevice]:
        records.sort(key=lambda item: (item.provider, item.provider_device_id, item.canonical_id))
        keys = [self._identity_keys(item) for item in records]
        pending = set(range(len(records)))
        components: list[list[int]] = []
        while pending:
            component = {min(pending)}
            changed = True
            while changed:
                changed = False
                related = {
                    candidate
                    for candidate in pending - component
                    if any(keys[candidate] & keys[current] for current in component)
                }
                if related:
                    component.update(related)
                    changed = True
            pending.difference_update(component)
            components.append(sorted(component))

        output: list[NormalizedDevice] = []
        for component in components:
            members = [records[index] for index in component]
            serials = {normalize_identity(item.serial_number) for item in members}
            imeis = {normalize_identity(item.imei) for item in members}
            serials.discard(None)
            imeis.discard(None)
            duplicate_provider = len({item.provider for item in members}) != len(members)
            cross_key_bridge = self._has_cross_key_bridge(members)
            conflict = (
                len(serials) > 1
                or len(imeis) > 1
                or duplicate_provider
                or cross_key_bridge
            )
            if conflict:
                for member in members:
                    member.identity_conflict = True
                    output.append(self._finalize_single(member, now))
            else:
                output.append(self._merge(members, now))
        return sorted(output, key=lambda item: item.canonical_id)

    @staticmethod
    def _has_cross_key_bridge(members: list[NormalizedDevice]) -> bool:
        serials = [normalize_identity(item.serial_number) for item in members]
        imeis = [normalize_identity(item.imei) for item in members]
        for index, (serial, imei) in enumerate(zip(serials, imeis)):
            if not serial or not imei:
                continue
            serial_matches = {
                other
                for other, value in enumerate(serials)
                if other != index and value == serial
            }
            imei_matches = {
                other
                for other, value in enumerate(imeis)
                if other != index and value == imei
            }
            if serial_matches and imei_matches and serial_matches.isdisjoint(imei_matches):
                return True
        return False

    @staticmethod
    def _identity_keys(device: NormalizedDevice) -> set[tuple[str, str]]:
        keys: set[tuple[str, str]] = set()
        serial = normalize_identity(device.serial_number)
        imei = normalize_identity(device.imei)
        if serial:
            keys.add(("serial", serial))
        if imei:
            keys.add(("imei", imei))
        return keys

    def _finalize_single(self, device: NormalizedDevice, now: datetime) -> NormalizedDevice:
        device.provider_refs = {device.provider: device.provider_device_id}
        device.provenance.update(
            {key: device.provider for key in device.inventory}
        )
        return device

    def _merge(self, members: list[NormalizedDevice], now: datetime) -> NormalizedDevice:
        members = sorted(members, key=lambda item: (item.provider, item.provider_device_id))
        merged = deepcopy(members[0])
        merged.provider_refs = {
            item.provider: item.provider_device_id for item in members
        }

        inventory: dict = {}
        provenance: dict[str, str] = {}
        for item in members:
            for key, value in sorted(item.inventory.items()):
                if key not in inventory and value is not None:
                    inventory[key] = deepcopy(value)
                    provenance[key] = item.provider
        merged.inventory = inventory
        merged.provenance.update(provenance)

        compliance = {item.compliant for item in members}
        merged.compliant = False if False in compliance else True if True in compliance else None

        locations = [item.location for item in members if item.location is not None]
        accepted = [
            location
            for location in locations
            if location.quality(
                now, self.max_location_age_seconds, self.max_accuracy_m
            )[0]
        ]
        choices = accepted or locations
        merged.location = min(choices, key=self._location_key) if choices else None
        return merged

    @staticmethod
    def _location_key(location: LocationEvidence) -> tuple[float, float, str]:
        try:
            observed = datetime.fromisoformat(
                (location.observed_at or "").replace("Z", "+00:00")
            ).timestamp()
        except (TypeError, ValueError, OverflowError):
            observed = float("-inf")
        accuracy = location.accuracy_m
        if not isinstance(accuracy, (int, float)) or isinstance(accuracy, bool):
            accuracy = float("inf")
        return (-observed, float(accuracy), location.provider)

    def fetch(self, now: datetime | None = None):
        from core.location_source import LocationReport

        sync = self.sync(now)
        reports: list[LocationReport] = []
        effective_now = now or datetime.now(timezone.utc)
        for device in sync.devices:
            accepted = False
            reason = "missing"
            if device.location is not None:
                accepted, reason = device.location.quality(
                    effective_now, self.max_location_age_seconds, self.max_accuracy_m
                )
            location = device.location
            reports.append(
                LocationReport(
                    device_id=device.canonical_id,
                    name=device.name,
                    platform=device.platform,
                    lat=location.lat if location and accepted else None,
                    lng=location.lng if location and accepted else None,
                    status=device.status,
                    compliant=device.compliant,
                    accuracy_m=location.accuracy_m if location else None,
                    last_seen=location.observed_at if location else None,
                    location_source=location.source if location else device.provider,
                    serial_number=device.serial_number,
                    imei=device.imei,
                    raw={
                        "provider": device.provider,
                        "provider_device_id": device.provider_device_id,
                        "provider_refs": deepcopy(device.provider_refs),
                        "provenance": deepcopy(device.provenance),
                        "identity_conflict": device.identity_conflict,
                        "location_quality": "accepted" if accepted else "rejected",
                        "location_rejection_reason": None if accepted else reason,
                    },
                )
            )
        return reports

    def execute(
        self,
        device: NormalizedDevice | dict,
        action: str,
        params: dict,
        dry_run: bool = False,
    ) -> dict:
        if isinstance(device, NormalizedDevice):
            references = device.provider_refs or {
                device.provider: device.provider_device_id
            }
            candidates = [
                name
                for name in sorted(references)
                if name in self._bindings
                and action in self._bindings[name].capabilities.actions
            ]
            provider = candidates[0] if candidates else device.provider
            remote_id = references.get(provider)
        else:
            provider = device.get("provider")
            references = device.get("provider_refs") or {}
            remote_id = device.get("provider_device_id") or references.get(provider)

        binding = self._bindings.get(provider)
        if binding is None:
            return {"ok": False, "error_type": "unknown_provider", "adapter": provider}
        if action not in binding.capabilities.actions or binding.execute_action is None:
            return {
                "ok": False,
                "error_type": "unsupported_action",
                "adapter": provider,
            }
        if not remote_id:
            return {
                "ok": False,
                "error_type": "missing_provider_device_id",
                "adapter": provider,
            }
        try:
            response = binding.execute_action(remote_id, action, params, dry_run)
        except Exception as exc:
            return {
                "ok": False,
                "error_type": "provider_error",
                "detail": type(exc).__name__,
                "adapter": provider,
            }
        if not isinstance(response, dict):
            return {
                "ok": False,
                "error_type": "invalid_provider_response",
                "adapter": provider,
            }
        return {**response, "adapter": provider}

    def health(self) -> dict[str, ProviderHealth]:
        return dict(self._health)
