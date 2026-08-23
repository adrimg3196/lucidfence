"""CAEP event builders for the LucidFence SSF Transmitter (Emisor, fase 1).

Builds device-compliance-change events from a RiskEngine evaluation. The event
is structured as a CAEP Security Event (SET) payload: a standard CAEP
``device-compliance-change`` object plus a namespaced LucidFence vendor
extension that carries the *explainability* signal (risk_score / severity /
reasons / fence_state) — our differentiator vs Jamf/Intune — without breaking
interoperability with strict CAEP consumers.

Local-first: no network calls. See DESIGN_EMISOR_CAEP_SSF.md (task t_66e64f3a).
"""

from __future__ import annotations

from typing import Any

# Canonical CAEP event-type URI (OpenID CAEP profile).
CAEP_DEVICE_COMPLIANCE_CHANGE = (
    "https://schemas.openid.net/secevent/caep/event-type/device-compliance-change"
)

# LucidFence vendor namespace for the explainability extension. Kept separate
# from the standard CAEP key so strict consumers ignore it gracefully.
LF_VENDOR_NS = "https://schemas.lucidfence.io/caep/device-compliance-change/v1"

# risk_score threshold above which a device is "non-compliant" (CAEP standard).
_NON_COMPLIANT_THRESHOLD = 70


def compliance_status_from_score(risk_score: int) -> str:
    """Map a 0-100 risk score to a CAEP compliance status string."""
    return "non-compliant" if risk_score > _NON_COMPLIANT_THRESHOLD else "compliant"


def build_device_compliance_change(
    device_id: str,
    *,
    risk_score: int,
    severity: str,
    reasons: list[str],
    fence_state: str | None = None,
) -> dict[str, Any]:
    """Build the CAEP ``device-compliance-change`` event object.

    Args are explicit (NOT a splatted evaluation dict) because
    ``RiskEngine.evaluate()`` returns extra keys (``policies``, ``signals``,
    ``provenance``...) that this builder does not accept — splatting would raise
    ``TypeError``. The caller threads only the fields we need.

    Returns a dict shaped for embedding under the events map of a SET:
        {
          "subject": {"subject_type": "device", "device_id": ...},
          "<CAEP uri>": {"current_status": ..., "compliance_status": ...,
                          "<LF_NS>": {"risk_score": ..., "severity": ...,
                                       "reasons": [...], "fence_state": ...}}
        }
    """
    compliance_status = compliance_status_from_score(int(risk_score))
    # This is the EVENT PAYLOAD — the value that gets wrapped under the
    # CAEP_URI key inside the SET's `events` map (see transmitter._build_set).
    return {
        "subject": {"subject_type": "device", "device_id": device_id},
        # CAEP-standard field (consumers expect current_status)
        "current_status": compliance_status,
        # vendor-friendly alias kept for clarity in our own tooling
        "compliance_status": compliance_status,
        # Explainability extension — the LucidFence differentiator
        LF_VENDOR_NS: {
            "risk_score": int(risk_score),
            "severity": severity,
            "reasons": list(reasons or []),
            "fence_state": fence_state,
        },
    }
