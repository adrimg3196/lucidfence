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

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_time = time  # alias so tests can monkeypatch time.time deterministically

from core.actions import build_adapter
from core.actions import VALID_ACTIONS
from core.fences import load_fences, fence_index, save_fences, Fence, validate_fences
from core.geo import Point
from core.location_source import build_location_source
from core.state_store import StateStore, DeviceState, now_iso
from core.policies import RiskEngine, load_policies, Policy, save_policies
from core.routes import load_routes, route_for_device, save_routes
from core.incidents import IncidentStore
from core import product as _product_mod
from core.cve import enrich_apps
from core.soar import evaluate_soar, DEFAULT_PLAYBOOKS


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
        # Cooldown (s) for destructive actions (wipe/lock/clear_passcode/reboot)
        # so a standing violation can't re-issue them every cycle/restart.
        self.action_cooldown_seconds = int(config.get("action_cooldown_seconds", 3600))
        self.data_dir = config.get("data_dir", "data")
        self.store = StateStore(self.data_dir)
        self.incidents = IncidentStore(self.data_dir)
        # Wire the incident lifecycle notifiers (Slack/Teams and/or Atomic Mail)
        # if configured. Both are tenant-local and never raise.
        webhook_url = config.get("incident_webhook_url", "") or ""
        if webhook_url:
            from core.notifier import IncidentNotifier
            self.incidents.notifier = IncidentNotifier(webhook_url=webhook_url)
        # Atomic Mail Agentic: real email for the SaaS (alerts + incidents +
        # digest). Opt-in per tenant: requires atomicmail config in integration.
        self.mailbox = None
        self._wire_atomicmail(config)
        _data_dir = config.get("data_dir", "data")
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
        # --- MOAT: Geospatial Risk & Policy Engine ---
        self.risk = RiskEngine(config.get("risk_signals_path"))
        # Nutrir CVEs desde feed NVD vivo/cacheado. Best-effort: nunca rompe el
        # arranque si la red/cache falla. Por defecto solo carga el cache local;
        # los runners con red (p. ej. cloud_publisher en GitHub Actions) pueden
        # activar `cve_feed_sync=True` para refrescarlo justo antes de cargarlo.
        try:
            from core.cve_feed_nvd import DEFAULT_OUT, load_nvd_feed_into_cve, sync_nvd_feed
            cve_feed_path = config.get("cve_feed_path") or DEFAULT_OUT
            if config.get("cve_feed_sync"):
                sync_nvd_feed(
                    apps=config.get("cve_feed_apps"),
                    out_path=cve_feed_path,
                    per_app=int(config.get("cve_feed_per_app", 5)),
                    timeout=int(config.get("cve_feed_timeout", 30)),
                    sleep_s=float(config.get("cve_feed_sleep_s", 0.4)),
                )
            load_nvd_feed_into_cve(cve_feed_path)
        except Exception:
            pass
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
        from core.alerts import AlertEngine
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
            from core.atomicmail_client import build_tenant_mailbox
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
            # If an incident email recipient is configured, wrap the mailbox in
            # an AtomicMailNotifier and attach it alongside any webhook notifier.
            if email_to and self.incidents.notifier is None:
                from core.notifier import AtomicMailNotifier
                self.incidents.notifier = AtomicMailNotifier(self.mailbox, to=email_to)
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
            stats = self.last_stats or {}
            devices = [s.to_dict() for s in self.store.snapshot().values()]
            total = len(devices)
            outside = sum(1 for d in devices if d.get("fence_state") == "outside")
            noncompliant = sum(1 for d in devices if d.get("compliant") is False)
            high_risk = sum(1 for d in devices if (d.get("risk_score") or 0) >= 70)
            lines = [
                f"Resumen LucidFence — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
                "",
                f"Dispositivos monitorizados: {total}",
                f"Fuera de geocerca: {outside}",
                f"Non-compliant: {noncompliant}",
                f"Riesgo alto (>=70): {high_risk}",
                "",
                "Dispositivos en riesgo:",
            ]
            for d in sorted(devices, key=lambda x: -(x.get("risk_score") or 0))[:10]:
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
        states_cur: dict[str, DeviceState] = {}
        events: list[dict] = []
        # Per-cycle action dedupe + accumulator: reset every cycle so a single
        # standing condition fires each action once per cycle, not once per
        # matching policy.
        self._cycle_actions = []
        self._cycle_fired = {}

        for rep in reports:
            try:
                loc = Point(lat=rep.lat, lng=rep.lng) if rep.lat is not None and rep.lng is not None else None
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
                    location_source=rep.location_source,
                    last_report_ts=now_iso(),
                    route_id=(assigned_route.id if assigned_route else None),
                    route_state=route_state,
                    route_deviation_m=route_dev_m,
                    apps=enrich_apps(rep.apps or []),
                    # --- IT inventory fields propagated from the location source ---
                    os_version=rep.os_version,
                    model=rep.model,
                    manufacturer=rep.manufacturer,
                    serial_number=rep.serial_number,
                    imei=rep.imei,
                    battery_level=rep.battery_level,
                    battery_state=rep.battery_state,
                    storage_total_gb=rep.storage_total_gb,
                    storage_free_gb=rep.storage_free_gb,
                    carrier=rep.carrier,
                    assigned_user=rep.assigned_user,
                    department=rep.department,
                    last_checkin=rep.last_checkin or rep.last_seen,
                    enrolled_at=rep.enrolled_at,
                    device_tag=rep.device_tag,
                    geofence_compliance=rep.geofence_compliance,
                )
                geo_snap = getattr(self.adapter, "geofence_compliance_snapshot", None)
                if callable(geo_snap):
                    snap = geo_snap(rep, fence_state=fence_state, fence_id=inside_fence)
                    if isinstance(snap, dict):
                        ds.geofence_compliance = snap
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
                })
                risk = self.risk.evaluate(risk_device, fence_state, risk_ctx)
                ds.risk_score = risk["risk_score"]
                ds.risk_severity = risk["severity"]
                fired_policies = self.risk.match_policies(self.policies, risk, ds.to_dict(), fence_state)
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

        # ---- SOAR: evaluate orchestration playbooks per device --------------
        # Each matched playbook yields UEM actions executed via the same adapter
        # (and cooldown/dry_run machinery) used for geofence actions.
        soar_ctx = {"cycle": self.cycle_count, "on_error": None}
        for ds in states_cur.values():
            dev_dict = ds.to_dict()
            try:
                execs = evaluate_soar(dev_dict, DEFAULT_PLAYBOOKS, soar_ctx)
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
        if self.adapter is not None:
            res = self.adapter.execute(ds, action, params or {}, dry_run=self.dry_run)
        else:
            # Modo simulation/dry-run sin adapter UEM real: la acción se registra
            # igual (es lo que promete el fallback de route_exit) sin ejecutar
            # nada externo.
            res = {"ok": True, "dry_run": True, "simulated": True,
                   "action": action, "device_id": ds.device_id}
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
        res = self.adapter.execute(dev, action, params or {}, dry_run=self.dry_run)
        res["ts"] = now_iso()
        res["fence_id"] = dev.inside_fence
        res["trigger"] = "operator"
        res["policy_name"] = "comando manual"
        res["operator"] = operator
        res["manual"] = True
        self.store.log_action(res)
        effective = bool(res.get("dry_run") or res.get("ok") or res.get("delegated"))
        if action in self.DESTRUCTIVE_ACTIONS and effective:
            self.store.record_action_at(dev.device_id, action, now)
        return res


    def _fire_actions(self, rep: Any, ds: DeviceState, prev: Optional[DeviceState], cur_key: str) -> list[dict]:
        fired: list[dict] = []
        fence_id, state = cur_key.split(":", 1)
        fence = self.fence_by_id.get(fence_id) if fence_id and fence_id != "none" else None
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
        if fence is None:
            return fired
        for act in fence.actions:
            if not act.enabled:
                continue
            if act.when != when:
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
                    from core import geocode
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
        from core.routes import Route, save_routes
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
        wps = [Point(lat=float(w["lat"]), lng=float(w["lng"])) for w in waypoint_data]
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
        from core.routes import save_routes
        self.routes = [r for r in self.routes if r.id != route_id]
        save_routes(self.routes_path, self.routes)

    # ---- policies / workflows (persisted to the tenant's policies.json) ----
    def add_policy(self, policy_dict: dict):
        """Persist a new policy (from a workflow template or custom builder)."""
        from core.policies import save_policies
        # drop any existing policy with the same id (idempotent apply)
        self.policies = [p for p in self.policies if p.id != policy_dict.get("id")]
        self.policies.append(Policy(**_policy_kwargs(policy_dict)))
        save_policies(self.policies_path, self.policies)

    def delete_policy(self, policy_id: str):
        from core.policies import save_policies
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
        }

    # ---- loop ------------------------------------------------------------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        # run immediately, then every interval
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception as exc:  # never let the loop die
                self.last_stats = {"error": str(exc), "ts": now_iso()}
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()

    # ---- risk context helpers -----------------------------------------
    def _ctx_hour(self):
        from datetime import datetime
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
        crit_apps = high_apps = vuln_apps = 0
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
        return {
            "apps_total": total_apps,
            "vulnerable_apps": vuln_apps,
            "critical_cve_apps": crit_apps,
            "high_cve_apps": high_apps,
        }
