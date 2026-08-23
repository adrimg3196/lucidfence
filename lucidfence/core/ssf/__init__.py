"""LucidFence SSF package — Emisor CAEP/SSF (fase 1 de P1).

Local-first Security Event Token (SET) emission: build a CAEP
device-compliance-change event from a RiskEngine evaluation, sign it as a JWS
(ES256, vendored key), and deliver it through the existing SignedWebhookNotifier.

Receptor (fase 2) y Streaming HTTP SSF endpoints (fase 3, OFF) no se incluyen
aquí. Ver DESIGN_EMISOR_CAEP_SSF.md (task t_66e64f3a).
"""

from __future__ import annotations

from lucidfence.core.ssf.caep_events import (
    CAEP_DEVICE_COMPLIANCE_CHANGE,
    LF_VENDOR_NS,
    build_device_compliance_change,
    compliance_status_from_score,
)
from lucidfence.core.ssf.keys import SIGNING_ALG, load_signing_jwk
from lucidfence.core.ssf.transmitter import SSFTransmitter

__all__ = [
    "SSFTransmitter",
    "build_device_compliance_change",
    "compliance_status_from_score",
    "CAEP_DEVICE_COMPLIANCE_CHANGE",
    "LF_VENDOR_NS",
    "SIGNING_ALG",
    "load_signing_jwk",
]
