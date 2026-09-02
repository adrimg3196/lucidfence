"""Geofencing engine: the brain of the product.

Pipeline per cycle:
  1. location_source.fetch()           -> list[LocationReport]
  2. evaluate each device vs fences    -> inside / outside / unknown
  3. diff against persisted prev state -> transitions (enter / exit / violation)
  4. for each transition, run the fence's configured UEM actions
  5. persist states, events and action log

Runs locally, forever, on the configured interval (default 15 min).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

_time = time  # alias so tests can monkeypatch time.time deterministically

from lucidfence.core.actions import build_adapter
from lucidfence.core.actions import VALID_ACTIONS
from lucidfence.core.adapters import build_bindings
from lucidfence.core.fences import load_fences, fence_index, save_fences, Fence, validate_fences
from lucidfence.core.geo import point_from
from lucidfence.core.location_source import build_location_source
from lucidfence.core.state_store import StateStore, DeviceState, now_iso
from lucidfence.core.policies import RiskEngine, load_policies, Policy, save_policies
from lucidfence.core.routes import load_routes, route_for_device, save_routes, Route
from lucidfence.core.risk_levels import count_high_risk
from lucidfence.core.declarative import resolve_declarative_subaction
from lucidfence.core.incidents import IncidentStore
from lucidfence.core.notifier import IncidentFanoutNotifier
from lucidfence.core import product as _product_mod
from lucidfence.core.cve import enrich_apps
from lucidfence.core.soar import evaluate_soar, DEFAULT_PLAYBOOKS
from lucidfence.core.osquery_posture import OsqueryPostureProvider
from lucidfence.core.location_integrity import assess as assess_location_integrity
from lucidfence.core.evidence_freshness import build_verifier


def _tag_route(res: Any, action: str, declarative: Optional[str],
               effective_dry: bool) -> Any:
    """Marca en el resultado la vía por la que salió la orden (auditable).

    `enforcement` es "declarative" o "imperative" en TODO resultado despachado;
    en el declarativo se conserva además la acción de política pedida
    (`requested_action`), porque el adapter devuelve la declarativa.
    """
    if not isinstance(res, dict):
        return res
    res["enforcement"] = "declarative" if declarative else "imperative"
    if declarative:
        res["requested_action"] = action
        # `apply_ddm` es offline (construye las declarations, no las sube) y no
        # marca `dry_run`. Sin esto, un lock declarativo en observe quedaría
        # registrado como ejecutado. La marca viene del gate del engine, que es
        # quien sabe que la orden no debía salir, no del adapter.
        if effective_dry:
            res.setdefault("dry_run", True)
    return res


def _policy_kwargs(d: dict) -> dict:
    """Extract only Policy dataclass fields from a workflow dict."""
    return {
        "id": d.get("id", "pol"),
        "name": d.get("name", "policy"),
        "description": d.get("description", ""),
        "when": d.get("when", []),
        "actions": d.get("actions", []),
        "enabled": bool(d.get("enabled", True)),
        "severity": d.get("severity", "medium"),
        "source": d.get("source"),
        "template_id": d.get("template_id"),
    }


class Engine:
    def __init__(self, config: dict):
        self.config = config
        self.org_id = config.get("applivery", {}).get("org_id", "")
        self.mode = config.get("mode", "simulation")  # simulation | live
        self.interval = int(config.get("interval_seconds", 900))
        self.dry_run = bool(config.get("dry_run", True))
        # --- Enforcement (piloto seguro) ---
        # Rollout progresivo pensado para admins reales: observe (todo dry-run,
        # solo incidentes) -> enforce con live_actions acotadas (p.ej. message
        # y lock) -> wipe solo con opt-in doble. `mode` manda sobre el legacy
        # `dry_run` si ambos están en config.
        enf = config.get("enforcement") or {}
        _mode = str(enf.get("mode") or "").strip().lower()
        if _mode == "observe":
            self.dry_run = True
        elif _mode == "enforce":
            self.dry_run = False
        _la = enf.get("live_actions")
        # None = sin lista: en enforce salen en vivo todas las acciones (legacy).
        self.live_actions = {str(a) for a in _la} if isinstance(_la, (list, tuple, set)) else None
        # wipe es la única acción irreversible: nunca sale en vivo sin
        # allow_wipe explícito, y wipe_allowlist puede acotarla a device_ids.
        self.allow_wipe = bool(enf.get("allow_wipe", False))
        self.wipe_allowlist = {str(x) for x in (enf.get("wipe_allowlist") or [])}
        # Cooldown (s) for destructive actions (wipe/lock/clear_passcode/reboot)
        # so a standing violation can't re-issue them every cycle/restart.
        self.action_cooldown_seconds = int(config.get("action_cooldown_seconds", 3600))
        self.data_dir = config.get("data_dir", "data")
        self.store = StateStore(self.data_dir)
        self.incidents = IncidentStore(self.data_dir)
        # Playbooks SOAR del tenant (REQ §5): builtin del producto + los del
        # tenant persistidos en <data_dir>/soar_playbooks.json. El engine los
        # fusiona en cada ciclo; un playbook roto se salta (auditado).
        from lucidfence.core.soar_playbook_store import TenantPlaybookStore
        self.soar_store = TenantPlaybookStore(data_dir=self.data_dir, builtin=DEFAULT_PLAYBOOKS)
        # Wire the incident lifecycle notifiers if configured: Slack/Teams
        # (incident_webhook_url, legacy) plus the multi-channel list
        # incident_webhooks (slack | generic firmado HMAC | ntfy). All are
        # tenant-local and never raise; Atomic Mail joins the fan-out below.
        from lucidfence.core.notifier import IncidentFanoutNotifier, build_incident_notifiers
        _channels = build_incident_notifiers(config)
        if len(_channels) == 1:
            self.incidents.notifier = _channels[0]
        elif _channels:
            self.incidents.notifier = IncidentFanoutNotifier(_channels)
        # Atomic Mail Agentic: real email for the SaaS (alerts + incidents +
        # digest). Opt-in per tenant: requires atomicmail config in integration.
        self.mailbox = None
        self._wire_atomicmail(config)
        _default_fences = config.get("fences_path")
        if _default_fences is None:
            _seed = config.get("sim_seed_path")
            if _seed:
                _default_fences = os.path.join(os.path.dirname(os.path.abspath(_seed)), "fences.json")
            else:
                # Repo root fences.json (sembrado por el server en modo live/demo).
                _default_fences = "fences.json"
        self.fences_path = Path(_default_fences)
        self.fences = load_fences(self.fences_path)
        self.fence_by_id = fence_index(self.fences)
        self.source = build_location_source(
            self.mode, self.org_id, config.get("sim_seed_path", "data/fleet_seed.json"),
            api_key=config.get("_applivery_api_key", ""),
            location_cfg=config.get("location_source"),
            # Geofencing lógico por red (portátiles sin GPS): inerte salvo que el
            # tenant declare `network_sites`. El resolver solo lee esa clave.
            network_cfg=config,
        )
        self.adapter = build_adapter(
            self.mode if not self.dry_run else "simulation",  # never call live in dry_run
            self.org_id,
            config.get("uem", {}).get(
                "action_endpoint_template", "/organizations/{org_id}/mdm/devices/{device_id}/commands"
            ),
            webhook_url=config.get("uem", {}).get("remediation_webhook_url", ""),
            api_key=config.get("_applivery_api_key", ""),
        )
        # Multi-UEM: if the tenant registered more than one provider, route
        # remediation actions to the right adapter by device provider_refs.
        # The orchestrator reuses the community MDMAdapter contract; when there
        # is only one (or zero) provider it stays inert and engine falls back
        # to the single self.adapter below.
        self.orchestrator = None
        providers = config.get("providers") or []
        if len(providers) > 1 or (len(providers) == 1 and providers[0].get("name") != "simulation"):
            try:
                from lucidfence.core.multiuem import MultiUEMOrchestrator
                self.orchestrator = MultiUEMOrchestrator(build_bindings(providers))
            except Exception:
                self.orchestrator = None
        # --- MOAT: Geospatial Risk & Policy Engine ---
        self.risk = RiskEngine(config.get("risk_signals_path"))
        # Optional endpoint posture evidence. osquery observes; LucidFence
        # correlates the evidence with geofences and UEM policy.
        self.osquery = OsqueryPostureProvider(config.get("osquery"))
        self.evidence_freshness = build_verifier(config.get("evidence_freshness"), self.data_dir)
        # Nutrir CVEs desde feed NVD vivo/cacheado. Best-effort: nunca rompe el
        # --- CVE feed (NVD cache / sync) ----------------------------------
        # SECURITY (fail-unknown, not fail-open): a broken or unavailable CVE
        # feed must surface as an explicit, observable error — never silently
        # degrade to "no vulnerabilities". A fail-open CVE loader would hide
        # real risk and let the vitrina publish a falsely clean posture. Any
        # exception here is logged and stored on status() so operators can see
        # the feed is unhealthy instead of trusting a silent zero. (task t_6479d79a)
        try:
            from lucidfence.core.cve_feed_nvd import load_nvd_feed_into_cve, sync_nvd_feed
            cve_feed_path = config.get("cve_feed_path")
            if not cve_feed_path:
                cve_feed_path = os.path.join(
                    self.data_dir, f"cve_feed_{self.org_id}.json"
                )
            loaded = 0
            if config.get("cve_feed_sync"):
                sync_nvd_feed(
                    apps=config.get("cve_feed_apps"),
                    out_path=cve_feed_path,
                    per_app=int(config.get("cve_feed_per_app", 5)),
                    timeout=int(config.get("cve_feed_timeout", 30)),
                    sleep_s=float(config.get("cve_feed_sleep_s", 0.4)),
                )
            loaded = load_nvd_feed_into_cve(cve_feed_path)
            self.cve_feed_load = {
                "ok": True,
                "entries": loaded,
                "path": cve_feed_path,
                "error": None,
            }
        except Exception as exc:  # fail-UNKNOWN: record, do NOT swallow silently
            logging.getLogger(__name__).error(
                "CVE feed load failed for org %s (path=%s): %s: %s",
                self.org_id, config.get("cve_feed_path"), type(exc).__name__, exc,
            )
            self.cve_feed_load = {
                "ok": False,
                "entries": 0,
                "path": config.get("cve_feed_path"),
                "error": f"{type(exc).__name__}: {exc}",
            }
        pol_path = config.get("policies_path", Path(self.data_dir) / "policies.json")
        self.policies_path = Path(pol_path)
        self.policies = load_policies(self.policies_path)
        # --- Route adherence module ---
        route_path = config.get("routes_path", "routes.json")
        rp = Path(route_path)
        if not rp.is_absolute():
            rp = Path(self.data_dir) / rp.name if "/" in route_path else Path(self.data_dir) / route_path
        self.routes_path = rp
        self.routes = load_routes(self.routes_path)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_run: Optional[str] = None
        self.cycle_count = 0
        self.last_stats: dict = {}
        # Cycle lock: prevents the autostart loop and an on-demand /api/run-once
        # from interleaving and corrupting the per-cycle accumulators / store.
        self._cycle_lock = threading.Lock()
        self._cycle_actions: list[dict] = []
        self._cycle_fired: dict[str, set] = {}
        # --- Configurable threshold alerts (MDM/UEM alerting) ---
        from lucidfence.core.alerts import AlertEngine
        self.alerts = AlertEngine(self.data_dir, mailer=self.mailbox)

    # ---- Atomic Mail Agentic wiring ------------------------------------
    def _wire_atomicmail(self, config: dict) -> None:
        """Build the tenant's Atomic Mail mailbox (real @atomicmail.ai inbox).

        Configuration is read from the tenant's ``integration.json`` (written by
        the SaaS settings endpoint). Opt-in only: if no atomicmail section is
        present, ``self.mailbox`` stays None and no email channel is active.
        Never raises — a bad/missing config simply disables the channel.
        """
        try:
            from lucidfence.core.atomicmail_client import build_tenant_mailbox
            am = config.get("atomicmail") or {}
            if not isinstance(am, dict):
                return
            username = am.get("username") or ""
            api_key = am.get("api_key") or ""
            email_to = am.get("incident_email_to") or am.get("email_to") or ""
            if not (username or api_key):
                return
            # Whitelabel: if the tenant has a FreeDomain domain configured, use
            # it as the sender/branding domain so mail goes out as
            # <username>@<whitelabel-domain> with SPF/DKIM aligned there.
            wl = config.get("whitelabel") or {}
            inbox_domain = (wl.get("domain") or "").strip() or None
            tdir = Path(self.data_dir)
            self.mailbox = build_tenant_mailbox(
                tdir, username=username or None, api_key=api_key or None,
                inbox_domain=inbox_domain,
            )
            # If an incident email recipient is configured, attach Atomic Mail
            # to the incident lifecycle. When a webhook is also configured,
            # fan out to both channels so real-time geofence exits still reach
            # email instead of being shadowed by the webhook notifier.
            if email_to:
                from lucidfence.core.notifier import AtomicMailNotifier, IncidentFanoutNotifier
                email_notifier = AtomicMailNotifier(self.mailbox, to=email_to)
                if self.incidents.notifier is None:
                    self.incidents.notifier = email_notifier
                else:
                    self.incidents.notifier = IncidentFanoutNotifier([
                        self.incidents.notifier,
                        email_notifier,
                    ])
            # Warm the session (register/recover) best-effort so the first
            # alert doesn't pay the PoW cost. Failures are tolerated.
            try:
                self.mailbox.ensure_registered()
            except Exception:
                pass
        except Exception:
            self.mailbox = None

    def send_digest(self, *, to: str | None = None, subject: str | None = None) -> bool:
        """Send a fleet + risk digest email via Atomic Mail.

        Returns True if delivered. Safe to call from a cron/periodic task; never
        raises. Requires the atomicmail channel to be configured.
        """
        if self.mailbox is None:
            return False
        try:
            devices = [s.to_dict() for s in self.store.snapshot().values()]
            total = len(devices)
            outside = sum(1 for d in devices if d.get("fence_state") == "outside")
            noncompliant = sum(1 for d in devices if d.get("compliant") is False)
            # count_high_risk NO cuenta risk_score=None como riesgo alto NI como bajo.
            high_risk = count_high_risk(devices, 70)
            unknown_risk = sum(1 for d in devices if d.get("risk_score") is None)
            lines = [
                f"Resumen LucidFence — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
                "",
                f"Dispositivos monitorizados: {total}",
                f"Fuera de geocerca: {outside}",
                f"Non-compliant: {noncompliant}",
                f"Riesgo alto (>=70): {high_risk}",
                f"Riesgo desconocido (sin señal): {unknown_risk}",
                "",
                "Dispositivos en riesgo:",
            ]
            for d in sorted(devices, key=lambda x: -(x.get("risk_score") or 0))[:10]:
                if d.get("risk_score") is None:
                    continue  # no inflar lo desconocido en el ranking de riesgo
                lines.append(
                    f"  - {d.get('name') or d.get('device_id')}: riesgo {d.get('risk_score') or 0} "
                    f"({d.get('fence_state')})"
                )
            text = "\n".join(lines)
            recipient = to or (self.config.get("atomicmail", {}) or {}).get("digest_email_to") or ""
            if not recipient:
                return False
            return self.mailbox.send(
                to=recipient,
                subject=subject or "[LucidFence] Digest de flota y riesgo",
                text=text,
            )
        except Exception:
            return False

    # ---- cycle -----------------------------------------------------------
    def _release_lock(self):
        # Idempotent: a cycle may release via an early return AND the
        # finally below; never raise if already released.
        try:
            self._cycle_lock.release()
        except RuntimeError:
            pass

    def run_once(self) -> dict:
        # Serialize cycles: the autostart loop and an on-demand /api/run-once
        # must never run concurrently (they share the per-cycle accumulators and
        # the state store). If a cycle is already in flight, skip rather than
        # interleave -- better to miss one on-demand tick than corrupt state.
        if not self._cycle_lock.acquire(blocking=False):
            return {"error": "cycle_in_progress", "ts": now_iso(), "mode": self.mode}
        try:
            if self.mode == "live" and not self.org_id:
                self.last_stats = {
                    "integration_error": {
                        "stage": "config",
                        "error": "org_id (workspace) no configurado en live mode",
                    },
                    "ts": now_iso(),
                    "mode": self.mode,
                    "devices_total": 0,
                }
                return self.last_stats
            reports = self.source.fetch()
        except Exception as exc:  # never let a flaky upstream API 500 the dashboard
            self._release_lock()
            self.last_stats = {
                "error": f"integration_error: {type(exc).__name__}: {exc}",
                "ts": now_iso(),
                "mode": self.mode,
            }
            return self.last_stats
        # Surface a captured (non-fatal) upstream error to the status payload so
        # the UI can show "Applivery rejected the token (HTTP 401)" instead of a
        # generic crash.
        src_err = getattr(self.source, "last_error", None)
        if src_err:
            self._release_lock()
            self.last_stats = {
                "integration_error": src_err,
                "ts": now_iso(),
                "mode": self.mode,
                "devices_total": 0,
            }
            return self.last_stats
        states_prev = self.store.snapshot()
        # Refresh once per cycle. A missing/stale log or binary never blocks
        # geofencing; provider health is exposed in cycle stats.
        self.osquery.refresh()
        states_cur: dict[str, DeviceState] = {}
        events: list[dict] = []
        # Per-cycle action dedupe + accumulator: reset every cycle so a single
        # standing condition fires each action once per cycle, not once per
        # matching policy.
        self._cycle_actions = []
        self._cycle_fired = {}

        for rep in reports:
            try:
                evidence_observed_at = now_iso()
                location_freshness = self.evidence_freshness.evaluate(
                    signal_type="location",
                    source=rep.location_source,
                    observed_at=evidence_observed_at,
                    evidence_ts=getattr(rep, "evidence_ts", None),
                    nonce=getattr(rep, "evidence_nonce", None),
                )
                freshness_gates_location = "location" in getattr(self.evidence_freshness, "windows", {})
                location_is_authoritative = (
                    not freshness_gates_location
                    or location_freshness.get("status") == "fresh"
                )

                loc = None
                if location_is_authoritative and rep.lat is not None and rep.lng is not None:
                    try:
                        loc = point_from({"lat": rep.lat, "lng": rep.lng})
                    except (TypeError, ValueError):
                        loc = None  # NaN/fuera de rango = desconocido, nunca "outside"
                inside_fence = None
                fence_state = "unknown"
                if loc is not None:
                    for f in self.fences:
                        if f.contains(loc):
                            inside_fence = f.id
                            fence_state = "inside"
                            break
                    if inside_fence is None:
                        fence_state = "outside"

                    # --- Route adherence: is this device on its assigned route? ---
                # Computed at device level (NOT inside `if loc is not None`) so a
                # GPS-less device is safely marked "unassigned" instead of crashing
                # the whole cycle with an unbound NameError.
                route_state = "unassigned"
                route_dev_m: Optional[float] = None
                assigned_route = route_for_device(self.routes, rep.device_id) if loc is not None else None
                if assigned_route is not None and loc is not None:
                    dev = assigned_route.distance_to(loc)
                    route_dev_m = round(dev, 1)
                    route_state = "off_route" if dev > assigned_route.corridor_m else "on_route"

                prev = states_prev.get(rep.device_id)
                # Anti-spoofing: verosimilitud del report contra el último
                # estado persistido (velocidad imposible, flip de país sin
                # movimiento, accuracy anómala). No descarta el report: deja
                # evidencia explicable y alimenta el Risk Engine.
                integrity = assess_location_integrity(
                    {"lat": rep.lat, "lng": rep.lng, "accuracy_m": rep.accuracy_m,
                     "country": rep.country, "location_source": rep.location_source,
                     "last_seen": rep.last_seen},
                    prev.to_dict() if prev else None,
                )
                posture = self.osquery.posture_for(
                    rep.device_id,
                    aliases=(
                        rep.serial_number or "",
                        str((rep.raw or {}).get("hostname") or ""),
                    ),
                )
                prev_key = (
                    f"{prev.inside_fence}:{prev.fence_state}" if prev else "none:unknown"
                )
                cur_key = f"{inside_fence}:{fence_state}"

                ds = DeviceState(
                    device_id=rep.device_id,
                    name=rep.name,
                    platform=rep.platform,
                    status=rep.status,
                    compliant=rep.compliant,
                    lat=rep.lat,
                    lng=rep.lng,
                    accuracy_m=rep.accuracy_m,
                    country=rep.country,
                    city=rep.city,
                    ip=rep.ip,
                    last_seen=rep.last_seen,
                    fence_id=inside_fence,
                    inside_fence=inside_fence,
                    fence_state=fence_state,
                    # Sin señal se conserva la última cerca conocida; con señal
                    # (inside/outside) la memoria es el propio veredicto.
                    last_inside_fence=(
                        ((prev.inside_fence or prev.last_inside_fence) if prev else None)
                        if fence_state == "unknown" else inside_fence
                    ),
                    location_source=rep.location_source,
                    last_report_ts=now_iso(),
                    route_id=(assigned_route.id if assigned_route else None),
                    route_state=route_state,
                    route_deviation_m=route_dev_m,
                    apps=enrich_apps(rep.apps or []),
                    # --- IT inventory fields propagated from the location source ---
                    os_version=posture.get("os_version") or rep.os_version,
                    model=posture.get("model") or rep.model,
                    manufacturer=posture.get("manufacturer") or rep.manufacturer,
                    serial_number=posture.get("serial_number") or rep.serial_number,
                    imei=rep.imei,
                    battery_level=posture.get("battery_level", rep.battery_level),
                    battery_state=posture.get("battery_state") or rep.battery_state,
                    storage_total_gb=posture.get("storage_total_gb", rep.storage_total_gb),
                    storage_free_gb=posture.get("storage_free_gb", rep.storage_free_gb),
                    encryption_enabled=posture.get("encryption_enabled", rep.encryption_enabled),
                    # La observación gana arriba; aquí se conserva intacto lo que
                    # el UEM afirmó, para poder contrastarlas (second_opinion.py).
                    uem_claimed_encryption=rep.encryption_enabled,
                    # DDM/UEM readback: carry None as None (unknown never fabricated).
                    lockdown_mode=rep.lockdown_mode,
                    supervised=rep.supervised,
                    hardware_health=rep.hardware_health,
                    carrier=rep.carrier,
                    assigned_user=rep.assigned_user,
                    department=rep.department,
                    last_checkin=rep.last_checkin or rep.last_seen,
                    enrolled_at=rep.enrolled_at,
                    device_tag=rep.device_tag,
                    geofence_compliance=rep.geofence_compliance,
                    management_mode=rep.management_mode,
                    ownership=rep.ownership,
                    location_integrity=integrity,
                    provider_refs=dict(rep.raw.get("provider_refs") or {}),
                    posture_source=posture.get("posture_source"),
                    posture_collected_at=posture.get("posture_collected_at"),
                    osquery_version=posture.get("osquery_version"),
                    osquery_config_valid=posture.get("osquery_config_valid"),
                    evidence_freshness={"location": location_freshness},
                    attestation=(
                        rep.attestation
                        if isinstance(rep.attestation, dict)
                        else (prev.attestation if prev is not None else None)
                    ),
                    identity_lineage=(
                        dict(rep.raw.get("identity_graph") or {})
                        if isinstance(rep.raw, dict) and isinstance(rep.raw.get("identity_graph"), dict)
                        else None
                    ),
                    identity_findings=(
                        list(rep.raw.get("identity_findings") or [])
                        if isinstance(rep.raw, dict) and isinstance(rep.raw.get("identity_findings"), list)
                        else []
                    ),
                )
                geo_snap = getattr(self.adapter, "geofence_compliance_snapshot", None)
                if callable(geo_snap):
                    snap = geo_snap(rep, fence_state=fence_state, fence_id=inside_fence)
                    if isinstance(snap, dict):
                        ds.geofence_compliance = snap
                # Carry the prior persisted risk verdict (headline + EXPLAIN)
                # into the freshly-built state. A transient evaluator crash in
                # the block below must NOT overwrite a previously-good verdict
                # with None — the cycle only refreshes these fields when the
                # evaluator succeeds, so the prior values stay authoritative
                # until then (the GET path falls back to a live recompute +
                # honest sentinel if the prior verdict is also absent).
                if prev is not None:
                    ds.risk_score = prev.risk_score
                    ds.risk_severity = prev.risk_severity
                    ds.risk_reasons = prev.risk_reasons
                    ds.risk_matched_policies = prev.risk_matched_policies
                    ds.risk_evaluated_at = prev.risk_evaluated_at
                    ds.risk_provenance = prev.risk_provenance
                    ds.risk_verified = prev.risk_verified
                # --- MOAT: riesgo compuesto + políticas ---
                risk_ctx = {
                    "hour": self._ctx_hour(),
                    "shift_zones": self._ctx_shift_zones(),
                    "zone_risk": self._ctx_zone_risk(),
                }
                risk_device = dict(rep.__dict__ if hasattr(rep, "__dict__") else vars(rep))
                risk_device.update({
                    "fence_id": inside_fence,
                    "inside_fence": inside_fence,
                    "fence_state": fence_state,
                    "route_id": assigned_route.id if assigned_route else None,
                    "route_state": route_state,
                    "route_deviation_m": route_dev_m,
                    "evidence_freshness": ds.evidence_freshness,
                })
                risk_device.update(posture)
                risk_device["location_integrity"] = integrity
                try:
                    risk = self.risk.evaluate(risk_device, fence_state, risk_ctx)
                except Exception as _eval_exc:
                    # Defensive: a crashed evaluator must not break the whole
                    # cycle. Leave the persisted verdict explaining fields as-is
                    # (None on first cycle) so the GET path falls back to a live
                    # recompute + honest sentinel rather than masking the failure.
                    self.store.log_event({
                        "ts": now_iso(), "device_id": rep.device_id,
                        "kind": "risk_eval_error",
                        "error": f"{type(_eval_exc).__name__}: {_eval_exc}",
                    })
                    risk = None
                if risk is not None:
                    ds.risk_score = risk["risk_score"]
                    ds.risk_severity = risk["severity"]
                    # --- Defect 2: persist the EXPLAIN of the verdict so the
                    # GET path projects the exact "why" that fired actions. ---
                    ds.risk_reasons = list(risk.get("reasons") or [])
                    _fired = self.risk.match_policies(
                        self.policies, risk, ds.to_dict(), fence_state)
                    ds.risk_matched_policies = [fp["policy_id"] for fp in _fired]
                    ds.risk_evaluated_at = now_iso()
                    ds.risk_provenance = risk.get("provenance")
                    ds.risk_verified = risk.get("verified")
                    fired_policies = _fired
                else:
                    # Evaluator crashed: keep prior persisted fields so telemetry
                    # is not clobbered; the GET sentinel covers the display.
                    fired_policies = []
                for fp in fired_policies:
                    for act in fp.get("actions", []):
                        self._dedupe_action(ds, act.get("action"), inside_fence,
                                            f"policy:{fp['policy_id']}", fp["name"], fp["severity"],
                                            act.get("params", {}))
                states_cur[rep.device_id] = ds
                self.store.upsert(ds)
                self.store.log_trail(rep.device_id, rep.lat, rep.lng, fence_state, now_iso())

                # --- Route deviation is independent of fence state. Detect the
                # on_route -> off_route transition directly (NOT inside the
                # fence-transition block) so a device that leaves its corridor
                # while staying in the same geofence still fires route_exit. ---
                prev_route_state = (prev.route_state if prev else None)
                if prev_route_state == "on_route" and route_state == "off_route":
                    rev = {
                        "ts": now_iso(),
                        "device_id": rep.device_id,
                        "device_name": rep.name,
                        "kind": "route_exit",
                        "route_id": assigned_route.id if assigned_route else None,
                        "deviation_m": route_dev_m,
                    }
                    events.append(rev)
                    self.store.log_event(rev)
                    self._fire_route_exit(rep, ds, assigned_route, route_dev_m)

                if prev_key != cur_key:
                    ev = {
                        "ts": now_iso(),
                        "device_id": rep.device_id,
                        "device_name": rep.name,
                        "from": prev_key,
                        "to": cur_key,
                    }
                    events.append(ev)
                    self.store.log_event(ev)
                    # reset dwell timer on any transition
                    self.store.reset_dwell(rep.device_id)
                    # fire actions for the matching fence
                    self._fire_actions(rep, ds, prev, cur_key)
                else:
                    # No transition this cycle. Two standing-state behaviours matter:
                    # 1) Dwell time: accumulate how long the device has been in its
                    #    current fence state (used for dwell-threshold actions/rules).
                    # 2) Standing violation: a non-compliant device that remains inside
                    #    a restricted fence must still trigger remediation. The original
                    #    code had this branch as a no-op (`pass`); we now fire
                    #    `on_violation` actions for the fence it is inside, so a device
                    #    that is non-compliant while inside a restricted zone is
                    #    remediated every `violation_interval` cycles instead of never.
                    self.store.bump_dwell(rep.device_id, self.interval)
                    if fence_state == "inside" and rep.compliant is False and inside_fence:
                        fence = self.fence_by_id.get(inside_fence)
                        if fence is not None:
                            self._fire_standing_violation(rep, ds, fence)

            except Exception as _dev_exc:
                self.store.log_event({"ts": now_iso(), "device_id": getattr(rep, "device_id", "?"), "kind": "cycle_device_error", "error": f"{type(_dev_exc).__name__}: {_dev_exc}"})
                continue
        self.last_run = now_iso()

        # ---- SOAR: evaluate orchestration playbooks per device --------------\n        # Combina los playbooks builtin del producto con los del tenant (REQ §5).
        # Cada playbook matcheado produce acciones UEM. Las acciones destructivas
        # (lock/wipe/clear_passcode/reboot) son SIEMPRE human-gated: en lugar de
        # ejecutarlas, se emiten como handoff (diseño §5) y quedan registradas
        # para aprobación manual en la consola; nunca se ejecutan de forma
        # autónoma (REQ §5, design §2.3 / §5).
        soar_ctx = {"cycle": self.cycle_count, "on_error": None}
        playbooks = self.soar_store.all_playbooks()
        for ds in states_cur.values():
            dev_dict = ds.to_dict()
            try:
                execs = evaluate_soar(dev_dict, playbooks, soar_ctx)
            except Exception:
                execs = []
            for ex in execs:
                for act in ex.get("actions", []):
                    aname = act.get("action")
                    if not aname:
                        continue
                    # flag_app is a local enrichment marker; emit as an event only
                    if aname == "flag_app":
                        self.store.log_event({
                            "ts": now_iso(), "kind": "soar_flag",
                            "device_id": ds.device_id,
                            "playbook_id": ex.get("playbook_id"),
                            "note": act.get("params", {}).get("reason", ""),
                        })
                        continue
                    if aname in self.DESTRUCTIVE_ACTIONS:
                        # Human-gate: handoff, no ejecución autónoma.
                        self.store.log_event({
                            "ts": now_iso(), "kind": "soar_handoff",
                            "device_id": ds.device_id,
                            "playbook_id": ex.get("playbook_id"),
                            "playbook_name": ex.get("name"),
                            "action": aname,
                            "severity": ex.get("severity", "high"),
                            "matched_fields": ex.get("matched_fields", []),
                            "params": act.get("params", {}) or {},
                            "human_gate": True,
                            "note": "accion destructiva pausada para aprobacion manual (SOAR human-gate)",
                        })
                        # Registrar el handoff como su PROPIA entrada en la
                        # superficie por ciclo del SOC. NO se muta la acción
                        # previa (eso etiquetaba mal locate/notify como el
                        # handoff) y NO hay guarda condicional (si el handoff es
                        # la PRIMERA acción del ciclo — CVE crítico + fuera de
                        # perímetro —, la guarda `if self._cycle_actions` lo
                        # descartaba en silencio, dejando cero rastro en la
                        # lista del ciclo). executed/ok=False: un handoff no
                        # cuenta como ejecutado en stats ni arma cooldown (al
                        # aprobar el humano la orden debe poder salir ya).
                        self._cycle_actions.append({
                            "ts": now_iso(),
                            "device_id": ds.device_id,
                            "action": aname,
                            "soar": True,
                            "soar_handoff": True,
                            "human_gate": True,
                            "playbook_id": ex.get("playbook_id"),
                            "playbook_name": ex.get("name"),
                            "severity": ex.get("severity", "high"),
                            "executed": False,
                            "ok": False,
                            "dry_run": self.dry_run,
                            "note": "SOAR human-gate: pendiente de aprobacion manual",
                        })
                        continue
                    if self._dedupe_action(
                        ds, aname, "soar", ex.get("playbook_id", "soar"),
                        f"soar:{ex.get('name', '')}", ex.get("severity", "high"),
                        act.get("params", {}) or {},
                    ):
                        self._cycle_actions[-1]["soar"] = True
                        self._cycle_actions[-1]["playbook_id"] = ex.get("playbook_id")

        self.cycle_count += 1
        try:
            stats = self._stats(states_cur, events, self._cycle_actions)
            self.store.log_stats(stats)
            # Derive + merge incidents during the cycle so new incidents (and their
            # webhook notifications) fire at detection time, independent of UI polling.
            try:
                device_dicts = [s.to_dict() for s in states_cur.values()]
                derived = _product_mod.derive_incidents(device_dicts, events, [], [])
                self.incidents.merge(derived)
            except Exception:
                pass
            # --- Evaluate configurable threshold alerts against the current fleet.
            try:
                alert_firings = self.alerts.evaluate(device_dicts)
                stats["alert_firings"] = len(alert_firings)
            except Exception:
                stats["alert_firings"] = 0
            self.last_stats = stats
        finally:
            # Release the cycle lock on EVERY path (normal, early-return, or
            # exception) so a flaky downstream call can never deadlock
            # all future cycles. Idempotent via _release_lock().
            self._release_lock()
        return stats

    # Actions that physically alter a device and MUST be cooled so a standing
    # violation can't re-issue them every cycle or after a restart.
    DESTRUCTIVE_ACTIONS = {"wipe", "lock", "clear_passcode", "reboot"}

    def _declarative_route(self, dev: Any, action: str, params: dict, *, dry_run: bool = False) -> Optional[dict]:
        """Issue #89 (single-provider): route an eligible action through the
        declarative channel before the blind imperative command.

        Consults the adapter's ``supports_ddm``/``supports_dsc``/
        ``supports_amapi_policy`` flags together with the device's reported
        ``management_mode``/``ownership`` via the shared gate, and ALSO the
        DDM-capability gate (#205). When either says declarative we build the
        declaration through the adapter's builder (``_apply_ddm`` / ``_apply_dsc``
        / ``_apply_amapi``) and tag the result with ``enforcement="declarative"``,
        ``declarative_subaction`` and ``original_action``. The imperative
        command (lock/wipe/...) is NOT issued.

        Returns the declarative result, or ``None`` when the device is not
        eligible so the caller keeps its imperative fallback. Never raises.
        """
        adapter = self.adapter
        if adapter is None:
            return None
        supports = (
            bool(getattr(adapter, "supports_ddm", False)),
            bool(getattr(adapter, "supports_dsc", False)),
            bool(getattr(adapter, "supports_amapi_policy", False)),
        )
        if not any(supports):
            return None
        sub = resolve_declarative_subaction(
            dev, action, params or {},
            supports_ddm=supports[0], supports_dsc=supports[1],
            supports_amapi_policy=supports[2], adapter=adapter,
        )
        if sub is None:
            return None
        decl_params = dict(params or {})
        if "profile_url" not in decl_params:
            decl_params.setdefault("profile_url", getattr(adapter, "ddm_profile_url", "") or "")
        res = adapter.execute(dev, sub, decl_params, dry_run=dry_run)
        if isinstance(res, dict):
            res["enforcement"] = "declarative"
            res["declarative_path"] = "declarative"
            res["declarative_subaction"] = sub
            res["original_action"] = action
            res["requested_action"] = action
        return res

    def _execute_action(self, dev: Any, action: str, params: dict) -> dict:
        """Route a remediation command to the right UEM provider.

        Multi-UEM: when an orchestrator is wired and the device carries
        provider_refs (set by MultiUEMOrchestrator.fetch), dispatch to the
        provider that supports the action. Falls back to the single
        self.adapter (legacy single-provider path) otherwise. Never raises.
        """
        dev_id = getattr(dev, "device_id", "") or (
            dev.get("device_id", "") if isinstance(dev, dict) else "")
        # Guardarraíl de wipe: en vivo solo con allow_wipe, y si hay
        # allowlist, solo para esos device_ids. El resultado bloqueado queda
        # en el action log (auditable) y, al no ser ok/dry_run/delegated,
        # no arma el cooldown: habilitar la llave permite reintentar ya.
        if action == "wipe" and not self.dry_run:
            if not self.allow_wipe:
                return {
                    "ok": False, "blocked": True, "error_type": "wipe_not_allowed",
                    "adapter": getattr(self.adapter, "name", "none"),
                    "device_id": dev_id, "action": action,
                    "error": "wipe bloqueado por guardarrail: requiere "
                             "enforcement.allow_wipe: true en la config del tenant",
                }
            if self.wipe_allowlist and dev_id not in self.wipe_allowlist:
                return {
                    "ok": False, "blocked": True, "error_type": "wipe_not_allowed",
                    "adapter": getattr(self.adapter, "name", "none"),
                    "device_id": dev_id, "action": action,
                    "error": f"wipe bloqueado: {dev_id!r} no está en "
                             "enforcement.wipe_allowlist",
                }
        # Gating por acción: en enforce con live_actions, lo no listado se
        # ejecuta como dry-run (se registra qué HABRÍA pasado, no pasa).
        effective_dry = self.dry_run
        if not effective_dry and self.live_actions is not None and action not in self.live_actions:
            effective_dry = True
        refs = getattr(dev, "provider_refs", None)
        multi = self.orchestrator is not None and isinstance(refs, dict) and bool(refs)
        # Multi-UEM: el orquestador ejecuta el transporte, pero la DECISIÓN de
        # ruta declarativa vs imperativa la toma el engine (issue #89) sobre el
        # dispositivo rico, usando el adapter de la ref (route_adapter) y sus
        # flags supports_*. El orquestador recibe wire_action = (subacción
        # declarativa) o action, y el engine etiqueta el resultado con
        # enforcement vía _tag_route. Se delega el resto del gating (wipe,
        # observe/enforce, allow-list, cooldown, audit) al orquestador.
        if multi:
            first_provider, first_id = next(iter(refs.items()))
            route_adapter = self.orchestrator._bindings.get(first_provider)
            route_cls = None
            if route_adapter is not None:
                from lucidfence.core.adapters import ADAPTER_REGISTRY
                route_cls = ADAPTER_REGISTRY.get(route_adapter.name)
            supports = (
                bool(getattr(route_cls, "supports_ddm", False)) if route_cls else False,
                bool(getattr(route_cls, "supports_dsc", False)) if route_cls else False,
                bool(getattr(route_cls, "supports_amapi_policy", False)) if route_cls else False,
            )
            declarative = resolve_declarative_subaction(
                dev, action, params or {},
                supports_ddm=supports[0], supports_dsc=supports[1],
                supports_amapi_policy=supports[2], adapter=route_cls,
            )
            wire_action = declarative or action
            # The orchestrator expects a NormalizedDevice-shaped input
            # (provider + provider_device_id + provider_refs); DeviceState only
            # keeps provider_refs, so bridge the first ref into those fields.
            bridge = {
                "provider": first_provider,
                "provider_device_id": first_id,
                "provider_refs": refs,
                "platform": getattr(dev, "platform", None),
                "os_version": getattr(dev, "os_version", None),
                "management_mode": getattr(dev, "management_mode", None),
                "ownership": getattr(dev, "ownership", None),
            }
            res = self.orchestrator.execute(bridge, wire_action, params or {}, dry_run=effective_dry)
            if res.get("error_type") not in ("unknown_provider", "missing_provider_device_id"):
                return _tag_route(res, action, declarative, effective_dry)
        # Single-provider (issue #89): ruta declarativa antes de la imperativa.
        # El gate (core.declarative) consulta management_mode/ownership del
        # dispositivo y los flags supports_* del adapter. Si dice "declarative"
        # construye la declaration (DDM/DSC/AMAPI) y etiqueta el resultado; el
        # comando imperativo de bloqueo no se emite. "unknown"/"imperative" ->
        # cae al camino de siempre.
        if self.adapter is not None:
            decl = self._declarative_route(dev, action, params or {}, dry_run=effective_dry)
            if decl is not None:
                return decl
            return _tag_route(
                self.adapter.execute(dev, action, params or {}, dry_run=effective_dry),
                action, None, effective_dry)
        return {"ok": True, "dry_run": True, "simulated": True, "enforcement": "imperative",
                "action": action, "device_id": getattr(dev, "device_id", "")}

    def _dedupe_action(self, ds: DeviceState, action: str, fence_id, trigger: str,
                       policy_name: str, severity: str, params: dict = None) -> bool:
        """Fire an action once per (device, action) per cycle across all sources.

        Prevents a single standing condition (e.g. outside + rooted) from
        dispatching the same destructive command once per matching policy.

        Destructive actions additionally respect a persisted cooldown window
        (`self.action_cooldown_seconds`): once executed, the same (device,
        action) will not fire again until the window elapses -- even across
        cycles and server restarts. Non-destructive actions (notify/message/
        locate) are never cooled.

        Returns True if fired, False if deduped/cooled.
        """
        key = f"{ds.device_id}:{action}:{fence_id or '_'}"
        bucket = self._cycle_fired.setdefault(fence_id or "_", set())
        if key in bucket:
            return False
        # Persisted cooldown for destructive actions (survives restarts).
        if action in self.DESTRUCTIVE_ACTIONS and self.action_cooldown_seconds > 0:
            last = self.store.last_action_at(ds.device_id, action)
            now = _time.time()
            if last and (now - last) < self.action_cooldown_seconds:
                return False
        bucket.add(key)
        res = self._execute_action(ds, action, params)
        res["ts"] = now_iso()
        res["fence_id"] = fence_id
        res["trigger"] = trigger
        res["policy_name"] = policy_name
        res["severity"] = severity
        self._cycle_actions.append(res)
        self.store.log_action(res)
        # Persist the cooldown ONLY when the destructive action was actually
        # carried out: a real 2xx from the UEM, an accepted webhook delegation,
        # or an explicit dry-run. A failed attempt must NOT block retries for the
        # whole cooldown window.
        effective = bool(
            res.get("dry_run")
            or res.get("ok")
            or res.get("delegated")
        )
        if action in self.DESTRUCTIVE_ACTIONS and effective:
            self.store.record_action_at(ds.device_id, action, _time.time())
        return True

    def run_command(self, dev: DeviceState, action: str, params: dict = None,
                    operator: str = "operator") -> dict:
        """On-demand remote command issued from the dashboard by an operator.

        Respects the destructive-action cooldown so a manual `wipe` cannot be
        spammed, but never silently drops the command: if it is still inside the
        cooldown window the result clearly says so (the UI shows a cooldown
        notice). Records the operator + reason for the audit trail.
        """
        if action not in VALID_ACTIONS:
            return {"ok": False, "error": "accion no valida", "valid": sorted(VALID_ACTIONS)}
        now = _time.time()
        # Destructive cooldown check (manual commands honor the same guardrail).
        if action in self.DESTRUCTIVE_ACTIONS and self.action_cooldown_seconds > 0:
            last = self.store.last_action_at(dev.device_id, action)
            if last and (now - last) < self.action_cooldown_seconds:
                remaining = int(self.action_cooldown_seconds - (now - last))
                return {
                    "ok": False,
                    "cooldown": True,
                    "action": action,
                    "device_id": dev.device_id,
                    "remaining_seconds": remaining,
                    "error": f"comando {action} en cooldown; reintenta en {remaining}s",
                }
        res = self._execute_action(dev, action, params)
        res["ts"] = now_iso()
        res["fence_id"] = dev.inside_fence
        res["trigger"] = "operator"
        res["policy_name"] = "comando manual"
        res["operator"] = operator
        res["manual"] = True
        self.store.log_action(res)
        # Readback declarativo (issue #70): si el adapter devolvió
        # `device_state` (p.ej. `ddm_status`), se fusiona con el estado
        # persistido. Merge, no reemplazo: el status report puede llegar
        # parcial (Apple solo manda los items suscritos que cambiaron), así
        # que un campo ausente no pisa nada, un fallo (ok=False) no toca el
        # estado y dry_run nunca muta. Las claves sin campo en DeviceState
        # (p.ej. `ddm_errors`) no se persisten aquí pero quedan registradas
        # en el action log de la línea anterior.
        readback = res.get("device_state")
        if res.get("ok") and not self.dry_run and isinstance(readback, dict):
            target = self.store.get(dev.device_id) or dev
            merged = False
            for key, value in readback.items():
                if value is None or key == "device_id" or not hasattr(target, key):
                    continue
                setattr(target, key, value)
                merged = True
            if merged:
                self.store.upsert(target)
        effective = bool(res.get("dry_run") or res.get("ok") or res.get("delegated"))
        if action in self.DESTRUCTIVE_ACTIONS and effective:
            self.store.record_action_at(dev.device_id, action, now)
        return res


    def _fire_actions(self, rep: Any, ds: DeviceState, prev: Optional[DeviceState], cur_key: str) -> list[dict]:
        fired: list[dict] = []
        fence_id, state = cur_key.split(":", 1)
        # Salto directo cerca A -> cerca B en un mismo ciclo: A se ABANDONA,
        # así que sus on_exit disparan primero (antes solo salía on_enter(B)
        # y el "avísame al salir del almacén" se perdía en silencio).
        if state == "inside" and prev is not None and prev.inside_fence and prev.inside_fence != fence_id:
            left = self.fence_by_id.get(prev.inside_fence)
            if left is not None:
                for act in left.actions:
                    if act.enabled and act.when == "on_exit" and self._dedupe_action(
                            ds, act.action, left.id, "on_exit", f"fence:{left.name}", "medium", act.params):
                        fired.append(self._cycle_actions[-1])
        # Determine which 'when' this transition matches
        when = None
        if state == "inside":
            when = "on_enter"
        elif state == "outside":
            when = "on_exit"
        elif state == "unknown":
            when = "on_unknown"
        if prev is None:
            # first sighting; only act on enter if a fence is known
            if state != "inside":
                when = None
        if state == "inside":
            fence = self.fence_by_id.get(fence_id)
        else:
            # Al salir (o perder señal), cur_key es "None:outside": la cerca
            # cuyo on_exit/on_unknown importa es la que se ABANDONA — la del
            # estado anterior. Resolver por cur_key hacía que esas acciones
            # no dispararan JAMAS (el bug que motivó este bloque).
            # Si el dispositivo estuvo "unknown" entre medias (inside -> unknown
            # -> outside), la cerca abandonada vive en last_inside_fence.
            prev_fence_id = (prev.inside_fence or prev.last_inside_fence) if prev else None
            fence = self.fence_by_id.get(prev_fence_id) if prev_fence_id else None
        if fence is None:
            return fired
        for act in fence.actions:
            if not act.enabled:
                continue
            if act.when != when:
                continue
            if when == "on_unknown" and act.action in self.DESTRUCTIVE_ACTIONS:
                # Desconocido nunca penaliza: perder señal no es evidencia y
                # jamás justifica lock/wipe/reboot/clear_passcode (defensa en
                # profundidad; validate_fences ya rechaza esa configuración).
                continue
            if self._dedupe_action(ds, act.action, fence.id, when, f"fence:{fence.name}", "medium", act.params):
                fired.append(self._cycle_actions[-1])
        return fired

    def _fire_route_exit(self, rep: Any, ds: DeviceState, route: Any, deviation_m: Optional[float]) -> list[dict]:
        """Fire a route-deviation action when a device leaves its corridor.

        Reuses the device's configured route alert action from the route's
        `on_exit` list; falls back to a notify so the event is always visible.
        """
        fired: list[dict] = []
        acts = getattr(route, "actions", None) or []
        if not acts:
            acts = [{"action": "notify", "params": {
                "channel": "security",
                "msg": f"Desviación de ruta: {deviation_m} m fuera del corredor",
            }}]
        for act in acts:
            if not act.get("enabled", True):
                continue
            if act.get("when") not in (None, "on_exit"):
                continue
            if self._dedupe_action(ds, act.get("action"), f"route:{getattr(route, 'id', '')}",
                                  "route_exit", f"ruta:{getattr(route, 'id', '')}", "medium", act.get("params", {})):
                fired.append(self._cycle_actions[-1])
        return fired

    # ---- tenant-local geofence CRUD ------------------------------------
    def add_fence(self, data: dict) -> Fence:
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("name es obligatorio")
        fence_type = data.get("type", "circle")
        raw = dict(data)
        raw["id"] = data.get("id") or f"fence-{int(time.time()*1000)}"
        raw["name"] = name
        raw["type"] = fence_type
        # Accept the compact UI payload {lat,lng} as well as canonical center.
        if fence_type == "circle" and not raw.get("center"):
            if data.get("lat") is not None and data.get("lng") is not None:
                raw["center"] = {"lat": data["lat"], "lng": data["lng"]}
            elif data.get("address"):
                # Free geocoding (Nominatim/OSM, no API key) -> coords.
                try:
                    from lucidfence.core import geocode
                    hit = geocode.geocode(data["address"])
                    if hit:
                        raw["center"] = {"lat": hit["lat"], "lng": hit["lon"]}
                        raw["address_resolved"] = hit["label"]
                except Exception:
                    pass  # operator may supply coords later
        try:
            fence = Fence.from_raw(raw)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"geovalla inválida: {exc}") from exc
        candidate = [f for f in self.fences if f.id != fence.id] + [fence]
        problems = validate_fences(candidate)
        if problems:
            raise ValueError("; ".join(problems))
        self.fences = candidate
        self.fence_by_id = fence_index(self.fences)
        save_fences(self.fences_path, self.fences)
        return fence

    def delete_fence(self, fence_id: str) -> bool:
        before = len(self.fences)
        self.fences = [f for f in self.fences if f.id != fence_id]
        if len(self.fences) == before:
            return False
        self.fence_by_id = fence_index(self.fences)
        save_fences(self.fences_path, self.fences)
        return True

    # ---- routes ---------------------------------------------------------
    def add_route(self, data: dict):
        """Create a route from API payload and persist it."""
        if not data.get("name"):
            raise ValueError("name es obligatorio")
        waypoint_data = list(data.get("waypoints") or [])
        if not waypoint_data and data.get("fence_ids"):
            for fence_id in data.get("fence_ids") or []:
                fence = self.fence_by_id.get(fence_id)
                if fence and fence.center:
                    waypoint_data.append({"lat": fence.center.lat, "lng": fence.center.lng})
        if not waypoint_data:
            raise ValueError("waypoints o fence_ids con centro son obligatorios")
        rid = data.get("id") or f"route-{int(time.time()*1000)}"
        wps = [point_from(w) for w in waypoint_data]  # NaN/fuera de rango -> ValueError (400)
        schedule = data.get("schedule")
        if schedule is None and (data.get("window_start") or data.get("window_end")):
            schedule = {"start": data.get("window_start"), "end": data.get("window_end")}
        r = Route(
            id=rid,
            name=data["name"],
            waypoints=wps,
            corridor_m=float(data.get("corridor_m", 200.0)),
            device_ids=list(data.get("device_ids", [])),
            schedule=schedule,
            color=data.get("color", "#3b82f6"),
        )
        self.routes.append(r)
        save_routes(self.routes_path, self.routes)

    def delete_route(self, route_id: str):
        self.routes = [r for r in self.routes if r.id != route_id]
        save_routes(self.routes_path, self.routes)

    # ---- policies / workflows (persisted to the tenant's policies.json) ----
    def add_policy(self, policy_dict: dict):
        """Persist a new policy (from a workflow template or custom builder)."""
        # drop any existing policy with the same id (idempotent apply)
        self.policies = [p for p in self.policies if p.id != policy_dict.get("id")]
        self.policies.append(Policy(**_policy_kwargs(policy_dict)))
        save_policies(self.policies_path, self.policies)

    def delete_policy(self, policy_id: str):
        self.policies = [p for p in self.policies if p.id != policy_id]
        save_policies(self.policies_path, self.policies)

    def active_workflows(self) -> list[dict]:
        """Policies that come from the Workflows module (template or custom)."""
        return [
            {**p.to_dict(), "active": p.enabled}
            for p in self.policies
            if getattr(p, "source", None) in ("template", "custom")
        ]

    def _fire_standing_violation(self, rep: Any, ds: DeviceState, fence: Any) -> list[dict]:
        """Remediate a non-compliant device that is still inside a restricted fence.

        Honors an optional `violation_interval_cycles` on the fence so we do not
        spam actions every single cycle; default is to act every 1 cycle (i.e.
        as soon as the violation state is detected and on each subsequent cycle
        once the dwell-based throttle allows it).
        """
        fired: list[dict] = []
        interval = int(fence.rules.get("violation_interval_cycles", 1))
        dwell_cycles = self.store.dwell_cycles(rep.device_id)
        if interval > 1 and (dwell_cycles % interval) != 0:
            return fired
        for act in fence.actions:
            if not act.enabled:
                continue
            if act.when != "on_violation":
                continue
            if self._dedupe_action(ds, act.action, fence.id, "on_violation", f"fence:{fence.name}", "high", act.params):
                fired.append(self._cycle_actions[-1])
        return fired

    def _stats(self, states: dict, events: list, actions: list) -> dict:
        n = len(states)
        inside = sum(1 for s in states.values() if s.fence_state == "inside")
        outside = sum(1 for s in states.values() if s.fence_state == "outside")
        unknown = sum(1 for s in states.values() if s.fence_state == "unknown")
        noncompliant = sum(1 for s in states.values() if s.compliant is False)
        critical = sum(1 for s in states.values() if s.risk_severity == "critical")
        high = sum(1 for s in states.values() if s.risk_severity == "high")
        off_route = sum(1 for s in states.values() if s.route_state == "off_route")
        on_route = sum(1 for s in states.values() if s.route_state == "on_route")
        ios_geo_total = sum(1 for s in states.values() if (s.geofence_compliance or {}).get("platform") == "ios")
        ios_geo_ok = sum(1 for s in states.values() if (s.geofence_compliance or {}).get("platform") == "ios" and (s.geofence_compliance or {}).get("compliant") is True)
        return {
            "cycle": self.cycle_count,
            "ts": self.last_run,
            "mode": self.mode,
            "dry_run": self.dry_run,
            "devices_total": n,
            "inside": inside,
            "outside": outside,
            "unknown": unknown,
            "non_compliant": noncompliant,
            "risk_critical": critical,
            "risk_high": high,
            "events_this_cycle": len(events),
            "actions_this_cycle": len(actions),
            "fences": len(self.fences),
            "policies": len(self.policies),
            "routes": len(self.routes),
            "routes_on_route": on_route,
            "routes_off_route": off_route,
            "ios_geofence_total": ios_geo_total,
            "ios_geofence_compliant": ios_geo_ok,
            "ios_geofence_noncompliant": max(ios_geo_total - ios_geo_ok, 0),
            "osquery_posture": self.osquery.status(),
            "enforcement": self.enforcement_status(),
        }

    def enforcement_status(self) -> dict:
        """Estado del rollout de enforcement, para status API y dashboard."""
        return {
            "mode": "observe" if self.dry_run else "enforce",
            "live_actions": sorted(self.live_actions) if self.live_actions is not None else "all",
            "allow_wipe": self.allow_wipe,
            "wipe_allowlist_size": len(self.wipe_allowlist),
        }

    def _egress_status(self) -> dict:
        """Summarize the tenant's outbound webhook egress policy for the UI.

        Reads the policy straight from the engine config (which is overlaid from
        integration.json by _apply_tenant_integration). Defaults to `permissive`
        so existing deployments are never reported as broken.
        """
        raw = (self.config or {}).get("egress_policy") or {}
        mode = str(raw.get("mode", "permissive")).strip().lower()
        if mode != "strict":
            return {"mode": "permissive", "allow": [], "allow_private": False}
        allow = raw.get("allow") or []
        if not isinstance(allow, list):
            allow = []
        return {
            "mode": "strict",
            "allow": [str(a) for a in allow if isinstance(a, str)],
            "allow_private": bool(raw.get("allow_private", False)),
        }

    def _webhook_delivery_status(self) -> dict:
        """Latest outgoing-webhook delivery outcome, including egress denials.

        Surfaces the most recent notifier result so the dashboard can show a
        `denied_by_egress_policy` outcome explicitly (never silent — criterion
        #3 of the product decision t_316b8ec5). Best-effort: never raises.
        """
        notifier = getattr(self.incidents, "notifier", None)
        if notifier is None:
            return {"configured": False, "last_result": None}
        last = getattr(notifier, "last_result", None)
        if isinstance(notifier, IncidentFanoutNotifier):
            # Fan-out: report the most recent per-channel snapshot.
            results = (last or {}).get("results") if isinstance(last, dict) else None
            return {
                "configured": True,
                "fanout": True,
                "last_result": last,
                "channels": [
                    {
                        "channel": (r.get("channel") if isinstance(r, dict) else None),
                        "ok": (r.get("ok") if isinstance(r, dict) else None),
                        "result": (r.get("last_result") if isinstance(r, dict) else None),
                    }
                    for r in (results or [])
                ],
            }
        return {"configured": True, "fanout": False, "last_result": last}

    # ---- loop ------------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception as exc:  # never let the loop die
                self.last_stats = {"error": str(exc), "ts": now_iso()}
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()

    # ---- risk context helpers -----------------------------------------
    def _ctx_hour(self):
        # Hora LOCAL del servidor, a propósito: en un producto local-first el
        # engine corre donde el admin, y "fuera de horario" significa SU
        # horario. Caveat asumido: en un despliegue cloud (runner UTC) la
        # señal off_hours se desplaza por el offset del huso; si eso importa,
        # la corrección va en config, no aquí en silencio.
        return datetime.now().hour

    def _ctx_shift_zones(self) -> dict:
        return self.config.get("shift_zones", {}) or {}

    def _ctx_zone_risk(self) -> dict:
        return self.config.get("zone_risk", {}) or {}

    def status(self) -> dict:
        return {
            "running": bool(self._thread and self._thread.is_alive()),
            "mode": self.mode,
            "interval_seconds": self.interval,
            "dry_run": self.dry_run,
            "enforcement": self.enforcement_status(),
            "egress_policy": self._egress_status(),
            "webhook_delivery": self._webhook_delivery_status(),
            "stats": self.last_stats,
            "fences": [
                {
                    "id": f.id,
                    "name": f.name,
                    "type": f.type,
                    "center": (
                        {"lat": f.center.lat, "lng": f.center.lng} if f.center else None
                    ),
                    "radius_m": f.radius_m,
                    "actions": [
                        {"action": a.action, "when": a.when, "enabled": a.enabled}
                        for a in f.actions
                    ],
                }
                for f in self.fences
            ],
            "devices": [
                {**s.to_dict(), "dwell_seconds": self.store.dwell_seconds(s.device_id)}
                for s in self.store.snapshot().values()
            ],
            "recent_events": self.store.recent_events(50),
            "recent_actions": self.store.recent_actions(50),
            "trails": {d.device_id: self.store.trail(d.device_id, 200)
                       for d in self.store.snapshot().values()},
            "routes": [
                {
                    "id": r.id,
                    "name": r.name,
                    "waypoints": [{"lat": w.lat, "lng": w.lng} for w in r.waypoints],
                    "corridor_m": r.corridor_m,
                    "device_ids": list(r.device_ids),
                    "color": r.color,
                }
                for r in self.routes
            ],
            "stats_history": self.store.stats_history(120),
            "cve_summary": self._cve_summary(),
            "cve_feed_load": getattr(self, "cve_feed_load", None),
            "ios_geofence_summary": self._ios_geofence_summary(),
        }

    def _ios_geofence_summary(self) -> dict:
        devices = [s for s in self.store.snapshot().values()
                   if (s.geofence_compliance or {}).get("platform") == "ios"]
        compliant = sum(1 for s in devices if (s.geofence_compliance or {}).get("compliant") is True)
        noncompliant = len(devices) - compliant
        return {
            "total": len(devices),
            "compliant": compliant,
            "noncompliant": noncompliant,
            "percent": round((compliant / len(devices) * 100), 1) if devices else 0,
            "mode": "simulated" if devices else None,
        }

    def _cve_summary(self) -> dict:
        """Fleet-wide CVE posture aggregated from persisted device apps."""
        devices = self.store.snapshot().values()
        crit_apps = high_apps = vuln_apps = unknown_apps = 0
        total_apps = 0
        for ds in devices:
            for a in (ds.apps or []):
                total_apps += 1
                if a.get("cves"):
                    vuln_apps += 1
                    sev = a.get("max_cve_severity")
                    if sev == "critical":
                        crit_apps += 1
                    elif sev == "high":
                        high_apps += 1
                    # "unknown" = no verifiable CVSS score: reported separately,
                    # never counted as critical/high (attribution integrity).
                    elif sev in (None, "unknown"):
                        unknown_apps += 1
        return {
            "apps_total": total_apps,
            "vulnerable_apps": vuln_apps,
            "critical_cve_apps": crit_apps,
            "high_cve_apps": high_apps,
            "unknown_cve_apps": unknown_apps,
        }
