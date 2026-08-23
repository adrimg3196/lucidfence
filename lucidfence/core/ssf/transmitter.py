"""SSF Transmitter (Emisor CAEP/SSF, fase 1 de P1).

Orchestrates the full emit path for a device-risk event:

    1) evaluate the device with RiskEngine (or an injected evaluate_fn)
    2) build a CAEP device-compliance-change event
    3) wrap it in a Security Event Token (SET) with iss/iat/jti
    4) sign the SET as a JWS (ES256, vendored key — local-first, no cloud)
    5) deliver via SignedWebhookNotifier (reuses the existing HMAC layer)

No network is required to *build/sign*; only the final webhook POST touches the
network, and that is delegated to SignedWebhookNotifier (which itself enforces
the egress allow-list).

See DESIGN_EMISOR_CAEP_SSF.md (task t_66e64f3a) for the full contract.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from lucidfence.core.policies import RiskEngine
from lucidfence.core.ssf import caep_events
from lucidfence.core.ssf.keys import SIGNING_ALG, load_signing_jwk

# Default issuer for locally-generated SETs.
DEFAULT_ISS = "https://lucidfence.local/ssf"


class _NotifierLike(Protocol):
    """Structural type for the delivery sink (duck-typed; SignedWebhookNotifier qualifies)."""

    def notify(self, transition: str, incident: dict) -> bool: ...

# Type of the callable used to turn (device, fence_state, ctx) into a dict
# shaped like RiskEngine.evaluate()'s return.
EvaluateFn = Callable[[dict, str, dict], dict]


class SSFTransmitter:
    def __init__(
        self,
        signing_jwk_path: Optional[Path] = None,
        notifier: Optional[_NotifierLike] = None,
        *,
        iss: str = DEFAULT_ISS,
        evaluate_fn: Optional[EvaluateFn] = None,
    ):
        self._jwk = load_signing_jwk(signing_jwk_path)
        self._notifier = notifier
        self._iss = iss
        # Production default: RiskEngine().evaluate. Tests inject a stub.
        self._evaluate = evaluate_fn or (lambda d, fs, c: RiskEngine().evaluate(d, fs, c))

    def emit_device_risk(
        self, device: dict, fence_state: str, ctx: dict | None = None
    ) -> dict[str, Any]:
        """Evaluate a device and emit a signed CAEP/SSF SET.

        Returns a dict with the signed JWS, the event payload, and the raw
        evaluation (handy for tests/auditing). Delivery success is reported by
        the notifier result inside the returned envelope only if a notifier is
        configured.
        """
        ctx = ctx or {}
        evaluation = self._evaluate(device, fence_state, ctx)

        event = caep_events.build_device_compliance_change(
            device.get("device_id") or evaluation.get("device_id") or "",
            risk_score=evaluation["risk_score"],
            severity=evaluation["severity"],
            reasons=evaluation.get("reasons", []),
            fence_state=fence_state,
        )
        set_claims = self._build_set(event)
        jws = self._sign_set(set_claims)

        envelope = {
            "jws": jws,
            "event": event,
            "evaluation": evaluation,
            "delivered": None,
        }
        if self._notifier is not None:
            ok = self._notifier.notify(
                "caep-device-compliance-change", {"jws": jws, "event": event}
            )
            envelope["delivered"] = bool(ok)
        return envelope

    def _build_set(self, event: dict) -> dict[str, Any]:
        """Wrap a CAEP event payload in a SET claim set."""
        return {
            "iss": self._iss,
            "iat": int(time.time()),
            "jti": str(uuid.uuid4()),
            "events": {caep_events.CAEP_DEVICE_COMPLIANCE_CHANGE: event},
        }

    def _sign_set(self, set_claims: dict) -> str:
        """Sign the SET as a JWS using the vendored ES256 key."""
        import jwt

        headers = {"kid": self._jwk.key_id, "typ": "secevent+jwt"}
        return jwt.encode(
            set_claims, self._jwk.key, algorithm=SIGNING_ALG, headers=headers
        )
