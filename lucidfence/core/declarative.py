"""Declarative-vs-imperative routing gate for the multi-UEM engine.

Issue #89 wires this into the action path; #88 is what makes it *useful* by
having adapters populate ``management_mode`` / ``ownership`` on every fetched
device. Until #88 those fields were ``None`` everywhere, so the gate below
fell through to ``imperative`` for every device in production — the "gate
declarativo" was wired but permanently dark.

The gate's contract (frozen): given an adapter that supports a declarative
channel (``supports_ddm`` / ``supports_dsc`` / ``supports_amapi_policy``) and a
device carrying a ``management_mode`` the UEM actually reported, it prefers the
declarative path. Symmetrically, if the UEM says the device is NOT in a
declarative-eligible management mode (e.g. a personal/BYOD device under an
EMM), the gate must NOT push a declaration the device would silently reject —
it returns ``imperative`` so the engine keeps issuing commands the UEM honours.

No inference: a missing ``management_mode`` means "we don't know", and the gate
returns ``unknown`` (NOT imperative) so the caller can apply its own policy
(e.g. prefer the safer imperative path, or refuse). Returning ``imperative``
only when we have positive evidence keeps us from silently downgrading
declarative-capable fleets.
"""
from __future__ import annotations

from typing import Any, Optional

__all__ = [
    "MANAGEMENT_MODES",
    "OWNERSHIPS",
    "declarative_path_for",
    "resolve_declarative_subaction",
]


def resolve_declarative_subaction(
    device: Any,
    action: str,
    params: dict,
    *,
    supports_ddm: bool = False,
    supports_dsc: bool = False,
    supports_amapi_policy: bool = False,
    adapter: Any = None,
) -> Optional[str]:
    """Pick the declarative sub-action for ``action`` on ``device``, or ``None``.

    See module history: combines the #89 management_mode/ownership gate with the
    legacy #205 DDM-capability gate so both routing contracts stay green.
    """
    if (supports_ddm or supports_dsc or supports_amapi_policy):
        if declarative_path_for(
            device,
            supports_ddm=supports_ddm,
            supports_dsc=supports_dsc,
            supports_amapi_policy=supports_amapi_policy,
        ) == "declarative":
            if supports_ddm and hasattr(adapter, "_apply_ddm"):
                return "apply_ddm"
            if supports_dsc and hasattr(adapter, "_apply_dsc"):
                return "apply_dsc"
            if supports_amapi_policy and hasattr(adapter, "_apply_amapi"):
                return "apply_amapi"
    if supports_ddm:
        try:
            from lucidfence.core.ddm import declarative_path_for as _ddm_path
            sub = _ddm_path(device, action, adapter, params or {})
            if sub:
                return sub
        except Exception:
            return None
    return None

# management_mode values an EMM/UEM actually reports. Mirrors the Android
# DevicePolicyManager / AMAPI ownership vocabulary (DEVICE_OWNER,
# PROFILE_OWNER, fully managed) and the Apple MDM/AMAPI equivalent. These are
# the only modes we accept; anything else is treated as "not declarative".
MANAGEMENT_MODES = (
    "device_owner",      # Android fully managed (DO) / AMAPI device-owner
    "profile_owner",     # Android work profile (PO) / AMAPI profile-owner
    "fully_managed",     # Apple/AMAPI fully-managed (supervised, ADE)
    "mdm",               # Apple legacy MDM enrolment
    "configurator",      # Apple Configurator (tethered) enrolment
)

# ownership values (who owns the device). "company" devices are eligible for
# declarative management; "employee_owned"/"byod" may be restricted.
OWNERSHIPS = (
    "company",
    "employee_owned",    # aka BYOD
    "unknown",
)


def _get(device: Any, key: str, default=None):
    if isinstance(device, dict):
        return device.get(key, default)
    return getattr(device, key, default)


def declarative_path_for(
    device: Any,
    *,
    supports_ddm: bool = False,
    supports_dsc: bool = False,
    supports_amapi_policy: bool = False,
) -> str:
    """Decide the action path for ``device`` given an adapter's declarative flags.

    Returns one of:
        "declarative"  — the adapter supports a declarative channel AND the
                         device's reported ``management_mode`` is an eligible
                         mode (and, for BYOD, the channel permits it).
        "imperative"   — positive evidence the device is NOT declarative-eligible
                         (e.g. a BYOD device under an EMM). The engine should
                         keep issuing commands the UEM honours.
        "unknown"      — we cannot tell (no ``management_mode`` populated, or the
                         adapter exposes no declarative channel). The caller
                         decides; the gate never silently downgrades.

    Rules:
        * No declarative adapter flag set -> "unknown" (nothing to route to).
        * ``management_mode`` missing/empty -> "unknown" (we don't infer).
        * Unknown ``management_mode`` value -> "unknown" (don't guess).
        * DDM/DSC: device_owner | profile_owner | fully_managed | mdm |
          configurator -> "declarative".
        * AMAPI policy passthrough: device_owner | profile_owner ->
          "declarative"; fully_managed maps to device_owner semantics on AMAPI.
        * employee_owned (BYOD) is NOT eligible for declarative push on most
          EMMs (the work profile is the only declarative surface, and that
          requires profile_owner, not employee_owned) -> "imperative".
    """
    if not (supports_ddm or supports_dsc or supports_amapi_policy):
        return "unknown"

    mode = _get(device, "management_mode", None)
    if not isinstance(mode, str) or not mode:
        return "unknown"
    if mode not in MANAGEMENT_MODES:
        return "unknown"

    ownership = _get(device, "ownership", None)
    if ownership == "employee_owned":
        # BYOD: declarative push is not honoured by the EMM for the whole
        # device; route imperatively so we don't ship a declaration the
        # device silently ignores.
        return "imperative"

    # DDM (Apple) accepts every enrolled/eligible mode.
    if supports_ddm and mode in ("fully_managed", "mdm", "configurator"):
        return "declarative"
    # DSC (Windows) applies to managed Windows.
    if supports_dsc and mode in ("fully_managed", "mdm"):
        return "declarative"
    # AMAPI policy passthrough (Android EMM). #90 fixes the exact adapter
    # flags once Intune/Workspace ONE passthrough is confirmed; the gate
    # already honours the vocabulary both expose.
    if supports_amapi_policy and mode in ("device_owner", "profile_owner", "fully_managed"):
        return "declarative"

    # Adapter declares a declarative channel but the device's mode isn't on
    # the eligible list for that channel -> don't push a declaration.
    return "imperative"
