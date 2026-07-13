"""Configurable threshold alerts for the local UEM command center.

IT admins want to be paged when something crosses a line they define — e.g.
a device outside its geofence for more than N minutes, risk score above X, or
any non-compliant device. This module:

  - stores per-tenant alert rules (threshold + channel) under data/tenants/<org>/
  - evaluates the current fleet snapshot every cycle (or on demand)
  - delivers via the configured channel (Slack/Teams incoming webhook or email
    via local SMTP) and records each firing in an audit log

Never raises: a bad webhook/SMTP config is recorded and skipped so the engine
cycle never 500s.
"""
from __future__ import annotations

import json
import smtplib
import threading
import time
from dataclasses import dataclass, field, asdict
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable, Optional

ALERT_TYPES = {
    "outside_duration",   # device outside geofence > minutes
    "risk_above",        # device risk score > threshold
    "noncompliant",      # device is non-compliant
    "battery_below",     # battery % below threshold
    "storage_low",       # free storage below threshold GB
    "stale_checkin",     # last check-in older than minutes
}

# Channels we currently support.
CHANNELS = {"slack", "email", "none"}

# Human labels (used by the UI) -> internal type keys. The frontend may send
# either the key or the label; add_rule normalizes both.
ALERT_TYPE_LABELS = {
    "outside_duration": "Fuera de geovalla > N min",
    "risk_above": "Riesgo > N",
    "noncompliant": "Dispositivo non-compliant",
    "battery_below": "Batería < N%",
    "storage_low": "Almacenaje libre < N GB",
    "stale_checkin": "Check-in antiguo > N min",
}
_LABEL_TO_KEY = {v: k for k, v in ALERT_TYPE_LABELS.items()}


def normalize_alert_type(value: str) -> str:
    """Accept either an internal key or a human label and return the key."""
    if not value:
        return ""
    v = str(value).strip()
    if v in ALERT_TYPES:
        return v
    if v in _LABEL_TO_KEY:
        return _LABEL_TO_KEY[v]
    # tolerant: case-insensitive match against labels/keys
    vl = v.lower()
    for k in ALERT_TYPES:
        if k.lower() == vl:
            return k
    for lab, k in _LABEL_TO_KEY.items():
        if lab.lower() == vl:
            return k
    return v  # let validation reject an unknown type


@dataclass
class AlertRule:
    id: str
    type: str
    threshold: float
    channel: str = "slack"          # slack | email | none
    target: str = ""                # webhook url (slack) or email address
    enabled: bool = True
    severity: str = "medium"        # low|medium|high|critical
    scope: str = "all"              # all | device_id | department | platform
    scope_value: str = ""
    cooldown_minutes: int = 30      # min time between repeat firings per rule+device

    def to_dict(self) -> dict:
        return asdict(self)


class AlertEngine:
    def __init__(self, data_dir: Path | str, http_post: Optional[Callable] = None):
        self.path = Path(data_dir) / "alert_rules.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._rules: dict[str, AlertRule] = {}
        self._firings: list[dict] = []
        self._last_fired: dict[str, float] = {}  # f"{rule_id}:{device_id}" -> ts
        self._post = http_post
        self._load()

    # ---- persistence ----------------------------------------------------
    def _load(self):
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
            self._rules = {str(r["id"]): AlertRule(**r) for r in rows}
        except Exception:
            self._rules = {}

    def _persist(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([r.to_dict() for r in self._rules.values()],
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ---- CRUD ------------------------------------------------------------
    def list_rules(self) -> list[dict]:
        with self.lock:
            return [r.to_dict() for r in self._rules.values()]

    def add_rule(self, rule: dict) -> AlertRule:
        rid = rule.get("id") or f"alert-{int(time.time()*1000)}"
        norm_type = normalize_alert_type(rule.get("type", ""))
        r = AlertRule(
            id=rid,
            type=norm_type,
            threshold=float(rule.get("threshold", 0)),
            channel=rule.get("channel", "slack"),
            target=rule.get("target", ""),
            enabled=bool(rule.get("enabled", True)),
            severity=rule.get("severity", "medium"),
            scope=rule.get("scope", "all"),
            scope_value=rule.get("scope_value", ""),
            cooldown_minutes=int(rule.get("cooldown_minutes", 30)),
        )
        if r.type not in ALERT_TYPES:
            raise ValueError(f"tipo de alerta no valido: {r.type}")
        if r.channel not in CHANNELS:
            raise ValueError(f"canal no valido: {r.channel}")
        with self.lock:
            self._rules[rid] = r
            self._persist()
        return r

    def delete_rule(self, rule_id: str) -> bool:
        with self.lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                self._persist()
                return True
        return False

    def recent_firings(self, limit: int = 100) -> list[dict]:
        with self.lock:
            return self._firings[-limit:][::-1]

    # ---- evaluation ------------------------------------------------------
    def _in_scope(self, rule: AlertRule, dev: dict) -> bool:
        if rule.scope in ("all", "", None):
            return True
        val = dev.get(rule.scope) or dev.get("department") if rule.scope == "department" else dev.get(rule.scope)
        return str(val or "") == str(rule.scope_value)

    def evaluate(self, devices: list[dict], now: float = None) -> list[dict]:
        """Evaluate all enabled rules against the current fleet snapshot.

        Returns the list of firings (also recorded in self._firings).
        """
        now = now or time.time()
        fired: list[dict] = []
        with self.lock:
            rules = [r for r in self._rules.values() if r.enabled]
        for dev in devices:
            did = str(dev.get("device_id") or "")
            # normalize helpful fields
            risk = float(dev.get("risk_score") or 0)
            battery = dev.get("battery_level")
            free_gb = dev.get("storage_free_gb")
            last_checkin = dev.get("last_checkin") or dev.get("last_seen")
            outside_min = 0.0
            if dev.get("fence_state") == "outside":
                dwell = dev.get("dwell_seconds") or 0
                outside_min = dwell / 60.0
            checkin_age_min = 0.0
            if last_checkin:
                try:
                    from datetime import datetime, timezone
                    ts = last_checkin.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(ts)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    checkin_age_min = (now - dt.timestamp()) / 60.0
                except Exception:
                    pass
            for rule in rules:
                if not self._in_scope(rule, dev):
                    continue
                triggered = False
                detail = ""
                if rule.type == "outside_duration":
                    triggered = outside_min >= rule.threshold
                    detail = f"fuera {outside_min:.0f} min (umbral {rule.threshold:.0f})"
                elif rule.type == "risk_above":
                    triggered = risk >= rule.threshold
                    detail = f"riesgo {risk:.0f} (umbral {rule.threshold:.0f})"
                elif rule.type == "noncompliant":
                    triggered = dev.get("compliant") is False
                    detail = "dispositivo non-compliant"
                elif rule.type == "battery_below":
                    triggered = battery is not None and battery < rule.threshold
                    detail = f"bateria {battery}% (umbral <{rule.threshold:.0f})"
                elif rule.type == "storage_low":
                    triggered = free_gb is not None and free_gb < rule.threshold
                    detail = f"libre {free_gb} GB (umbral <{rule.threshold:.0f})"
                elif rule.type == "stale_checkin":
                    triggered = checkin_age_min >= rule.threshold
                    detail = f"check-in hace {checkin_age_min:.0f} min (umbral {rule.threshold:.0f})"
                if not triggered:
                    continue
                key = f"{rule.id}:{did}"
                last = self._last_fired.get(key, 0)
                if (now - last) < (rule.cooldown_minutes * 60):
                    continue
                self._last_fired[key] = now
                firing = {
                    "rule_id": rule.id,
                    "rule_type": rule.type,
                    "device_id": did,
                    "device_name": dev.get("name") or did,
                    "severity": rule.severity,
                    "detail": detail,
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                    "channel": rule.channel,
                    "target": rule.target,
                }
                fired.append(firing)
                self._firings.append(firing)
                # deliver (never raises)
                self._deliver(rule, firing)
        return fired

    # ---- delivery --------------------------------------------------------
    def _deliver(self, rule: AlertRule, firing: dict) -> dict:
        if rule.channel == "none" or not rule.target:
            firing["delivered"] = False
            firing["delivery_note"] = "canal none o sin destino"
            return firing
        if rule.channel == "slack":
            payload = {
                "text": f"[{firing['severity'].upper()}] LucidFence: {firing['detail']}",
                "attachments": [{
                    "color": {"critical": "#b42318", "high": "#d92d20",
                              "medium": "#f79009", "low": "#2e90fa"}.get(firing["severity"], "#475467"),
                    "fields": [
                        {"title": "Dispositivo", "value": firing["device_name"], "short": True},
                        {"title": "Regla", "value": firing["rule_type"], "short": True},
                        {"title": "Detalle", "value": firing["detail"], "short": False},
                    ],
                    "footer": "LucidFence",
                }],
            }
            res = self._post_http(rule.target, payload) if self._post is None else self._post(rule.target, payload)
            firing["delivered"] = bool(res.get("ok")) if isinstance(res, dict) else False
            firing["delivery_result"] = res
            return firing
        if rule.channel == "email":
            return self._send_email(rule.target, firing)
        firing["delivered"] = False
        return firing

    def _post_http(self, url: str, payload: dict) -> dict:
        import http.client
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host, port = parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
        body = json.dumps(payload).encode("utf-8")
        try:
            if parsed.scheme == "https":
                import ssl
                ctx = ssl.create_default_context()
                conn = http.client.HTTPSConnection(host, port, timeout=10, context=ctx)
            else:
                conn = http.client.HTTPConnection(host, port, timeout=10)
            conn.request("POST", parsed.path or "/", body=body,
                         headers={"Content-Type": "application/json"})
            r = conn.getresponse()
            conn.close()
            return {"ok": 200 <= r.status < 300, "status": r.status}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def _send_email(self, to_addr: str, firing: dict,
                    smtp_host: str = "127.0.0.1", smtp_port: int = 25,
                    from_addr: str = "lucidfence@localhost") -> dict:
        msg = EmailMessage()
        msg["Subject"] = f"[LucidFence] {firing['severity'].upper()}: {firing['device_name']}"
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.set_content(
            f"Dispositivo: {firing['device_name']} ({firing['device_id']})\n"
            f"Regla: {firing['rule_type']}\n"
            f"Detalle: {firing['detail']}\n"
            f"Hora: {firing['ts']}\n"
        )
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as s:
                s.send_message(msg)
            firing["delivered"] = True
            return firing
        except Exception as exc:
            firing["delivered"] = False
            firing["delivery_result"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            return firing
