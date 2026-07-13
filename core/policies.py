"""Geospatial Risk & Policy Engine — el MOAT del producto.

Por qué existe (post-mortem PG): un UEM (Intune/Jamf/Applivery/Fleet) ya sabe la
ubicación del dispositivo. Si tu producto solo "dibuja geocercas y avisa", el UEM
lo absorbe en una sprint y desapareces. El moat es modelar el RIESGO como una
funcion compuesta de muchas señales que el UEM no combina:

    risk(device, context) = f(geofence_state, device_health, external_signals, time)

donde external_signals puede ser: turno del trabajador, hora del día, nivel de
riesgo de la zona (dataset externo), señal de red/IoT, estado de cumplimiento
histórico, etc. Eso produce:
  * un SCORE de riesgo continuo (0-100), no un binario dentro/fuera;
  * POLÍTICAS compuestas ("si fuera de geocerca AND no es su turno AND zona de
    riesgo alta -> riesgo crítico -> aislar dispositivo");
  * AUDITORÍA explicable: cada decisión tiene las señales que la provocaron.

Esto es lo que un comprador enterprise paga y lo que un adquirente (YC/strategic)
valora: una capa de política geoespacial que se sienta SOBRE cualquier UEM.

Todo local, sin exfiltrar datos. Las señales externas se cargan desde archivos
JSON locales (o se dejan en None para modo simulación).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

HERE = Path(__file__).resolve().parent
DEFAULT_SIGNALS_PATH = HERE.parent / "data" / "risk_signals.json"


# --------------------------------------------------------------------------
# Señales externas (pluggable). Un "signal provider" es cualquier función
# (device_state, ctx) -> dict de métricas. Se registran en tiempo de ejecución.
# --------------------------------------------------------------------------
SIGNAL_PROVIDERS: dict[str, Callable] = {}


def register_signal(name: str):
    """Decorator factory: @register_signal("name") def fn(device, ctx): ..."""
    def deco(fn: Callable):
        SIGNAL_PROVIDERS[name] = fn
        return fn
    return deco


def _safe_get(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d


# Señales por defecto (no requieren integración externa).
@register_signal("time_of_day")
def sig_time_of_day(device, ctx):
    hour = ctx.get("hour")
    if hour is None:
        return {"hour": None, "off_hours": False}
    off = hour < 7 or hour >= 20
    return {"hour": hour, "off_hours": off}


@register_signal("shift_match")
def sig_shift_match(device, ctx):
    """¿El dispositivo está donde debería según el turno? Requiere ctx['shift_zones']."""
    shift = ctx.get("shift_zones") or {}
    device_id = device.get("device_id")
    expected = shift.get(device_id)
    if not expected:
        return {"shift_known": False}
    actual_fence = device.get("fence_id")
    return {"shift_known": True, "shift_match": actual_fence == expected}


@register_signal("device_health")
def sig_device_health(device, ctx):
    return {
        "compliant": bool(device.get("compliant")),
        "rooted": bool(device.get("rooted", False)),
        "encryption": bool(device.get("encryption_enabled", True)),
        "os_outdated": bool(device.get("os_outdated", False)),
    }


@register_signal("device_posture")
def sig_device_posture(device, ctx):
    """Señales de posture del endpoint (inspirado en Fleet/osquery):
    disco casi lleno, batería crítica, SO sin parchear, sin cifrado.
    El Risk Engine las usa para penalizar el score de forma explicable."""
    free = device.get("storage_free_gb")
    total = device.get("storage_total_gb")
    battery = device.get("battery_level")
    os_ver = (device.get("os_version") or "").lower()
    encryption = bool(device.get("encryption_enabled", True))

    disk_low = False
    if free is not None and total:
        try:
            disk_low = (float(free) / float(total)) < 0.10  # <10% libre
        except (TypeError, ValueError):
            disk_low = False
    battery_critical = battery is not None and float(battery) <= 15
    # Heurística de SO sin parchear: versiones "antiguas" conocidas por plataforma.
    os_unpatched = any(tok in os_ver for tok in ("android 12", "android 11", "ios 15", "windows 10 ", "windows 10"))

    return {
        "disk_low": disk_low,
        "battery_critical": battery_critical,
        "os_unpatched": os_unpatched,
        "encryption_off": not encryption,
    }


@register_signal("zone_risk")
def sig_zone_risk(device, ctx):
    """Riesgo de la zona desde ctx['zone_risk'] (dataset externo opcional)."""
    zr = ctx.get("zone_risk") or {}
    fence = device.get("fence_id")
    risk = zr.get(fence, {}).get("risk") if fence else None
    return {"zone_risk": risk if risk is not None else 0.0}


@register_signal("route_state")
def sig_route_state(device, ctx):
    """Adherencia a ruta asignada. Expuesto para el dashboard y el score."""
    rs = device.get("route_state")
    dev = device.get("route_deviation_m")
    return {
        "route_state": rs,                       # on_route|off_route|unassigned
        "route_deviation_m": dev if dev is not None else 0.0,
        "route_id": device.get("route_id"),
    }


# --------------------------------------------------------------------------
# Política compuesta
# --------------------------------------------------------------------------
@dataclass
class Policy:
    id: str
    name: str
    description: str
    # lista de condiciones; todas deben cumplirse (AND) para disparar
    when: list[dict]
    # acciones a ejecutar (se pasan al adapter del engine)
    actions: list[dict] = field(default_factory=list)
    enabled: bool = True
    severity: str = "medium"  # low | medium | high | critical
    # workflow provenance (set by the Workflows module; None for hand-written policies)
    source: Optional[str] = None  # "template" | "custom" | None
    template_id: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "when": self.when,
            "actions": self.actions,
            "enabled": self.enabled,
            "severity": self.severity,
        }
        if self.source is not None:
            d["source"] = self.source
        if self.template_id is not None:
            d["template_id"] = self.template_id
        return d


def load_policies(path: Path) -> list[Policy]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for p in raw:
        out.append(Policy(
            id=p.get("id", "pol"),
            name=p.get("name", "policy"),
            description=p.get("description", ""),
            when=p.get("when", []),
            actions=p.get("actions", []),
            enabled=bool(p.get("enabled", True)),
            severity=p.get("severity", "medium"),
            source=p.get("source"),
            template_id=p.get("template_id"),
        ))
    return out


def save_policies(path: Path, policies: list[Policy]) -> None:
    """Persist the policy list (used by the Workflows module to add/remove)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps([p.to_dict() for p in policies], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# --------------------------------------------------------------------------
# Motor de riesgo
# --------------------------------------------------------------------------
class RiskEngine:
    def __init__(self, signals_path: Optional[Path] = None):
        self.signals_path = Path(signals_path) if signals_path else DEFAULT_SIGNALS_PATH
        self.external_signals: dict = self._load_external()

    def _load_external(self) -> dict:
        try:
            return json.loads(self.signals_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def evaluate(self, device: dict, fence_state: str, ctx: dict) -> dict:
        """Devuelve score de riesgo (0-100), señales y políticas disparadas."""
        # Reúne señales de todos los providers registrados
        signals: dict[str, Any] = {}
        for name, fn in SIGNAL_PROVIDERS.items():
            try:
                signals[name] = fn(device, ctx)
            except Exception:
                signals[name] = {}

        # --- score compuesto ---
        score = 0.0
        reasons: list[str] = []

        if fence_state == "outside":
            score += 35; reasons.append("fuera de geocerca permitida")
        elif fence_state == "unknown":
            score += 20; reasons.append("ubicación desconocida (señal perdida)")

        if not signals.get("device_health", {}).get("compliant", True):
            score += 25; reasons.append("dispositivo no conforme")
        if signals.get("device_health", {}).get("rooted"):
            score += 15; reasons.append("dispositivo con root/jailbreak")
        if signals.get("device_health", {}).get("os_outdated"):
            score += 10; reasons.append("SO desactualizado")

        # Posture del endpoint (estilo Fleet/osquery): penaliza estados de salud
        # del dispositivo que un MDM nativo no correlaciona con georriesgo.
        posture = signals.get("device_posture", {})
        if posture.get("disk_low"):
            score += 8; reasons.append("disco casi lleno (<10% libre)")
        if posture.get("battery_critical"):
            score += 6; reasons.append("batería crítica (≤15%)")
        if posture.get("os_unpatched"):
            score += 12; reasons.append("SO sin parchear de seguridad")
        if posture.get("encryption_off"):
            score += 15; reasons.append("almacenamiento sin cifrar")

        if signals.get("time_of_day", {}).get("off_hours"):
            score += 10; reasons.append("fuera de horario laboral")
        if signals.get("shift_match", {}).get("shift_known") and not signals.get("shift_match", {}).get("shift_match"):
            score += 20; reasons.append("dispositivo fuera de su turno asignado")

        zr = signals.get("zone_risk", {}).get("zone_risk", 0.0) or 0.0
        if zr:
            score += float(zr) * 20; reasons.append(f"zona de riesgo elevado ({zr})")

        # Route deviation: off-route commercial device is a distinct signal
        rs = signals.get("route_state", {})
        if rs.get("route_state") == "off_route":
            dev_m = float(rs.get("route_deviation_m", 0.0) or 0.0)
            # severity scales with how far off the corridor the device is
            pts = 25 + min(25, int(dev_m / 100.0))
            score += pts
            reasons.append(f"desviado de su ruta asignada ({int(dev_m)} m)")
        elif rs.get("route_state") == "on_route":
            score = max(0.0, score - 5)  # small credit for adhering to plan

        score = max(0.0, min(100.0, score))

        # --- Evidence gate (patrón T3MP3ST: un claim no es válido sin provenancia) ---
        # Un score de riesgo SOLO se considera "verified" si está respaldado por
        # señales/provenance reales (reasons no vacío). Un score > 0 sin razón es
        # un overclaim y se marca como no verificado (honest by construction).
        provenance = "tool" if reasons else "none"
        verified = bool(reasons)  # el score lleva su justificación o no cuenta como hallazgo
        if score > 0 and not reasons:
            # Salvaguarda: nunca emitir riesgo sin explicación.
            reasons.append("riesgo sin señal explícita (score base)")
            provenance = "context"
            verified = False

        # severidad derivada
        if score >= 80:
            severity = "critical"
        elif score >= 55:
            severity = "high"
        elif score >= 30:
            severity = "medium"
        else:
            severity = "low"

        return {
            "device_id": device.get("device_id"),
            "risk_score": round(score, 1),
            "severity": severity,
            "fence_state": fence_state,
            "signals": signals,
            "reasons": reasons,
            "provenance": provenance,
            "verified": verified,
        }

    def match_policies(self, policies: list[Policy], risk: dict, device: dict, fence_state: str) -> list[dict]:
        fired = []
        for pol in policies:
            if not pol.enabled:
                continue
            if self._all_conditions(pol.when, risk, device, fence_state):
                fired.append({
                    "policy_id": pol.id,
                    "name": pol.name,
                    "severity": pol.severity,
                    "description": pol.description,
                    "actions": pol.actions,
                })
        return fired

    @staticmethod
    def _all_conditions(conds: list[dict], risk: dict, device: dict, fence_state: str) -> bool:
        for c in conds:
            field_ = c.get("field")  # p.ej. "risk_score", "fence_state", "severity", "signal:zone_risk.zone_risk"
            op = c.get("op", "gte")
            val = c.get("value")
            actual = _resolve_field(field_, risk, device, fence_state)
            if actual is None:
                return False
            if not _cmp(actual, op, val):
                return False
        return True


def _resolve_field(field_: str, risk: dict, device: dict, fence_state: str):
    if field_ == "risk_score":
        return risk.get("risk_score")
    if field_ == "fence_state":
        return fence_state
    if field_ == "severity":
        return risk.get("severity")
    if field_ == "compliant":
        return device.get("compliant")
    if field_.startswith("signal:"):
        # signal:<provider>.<key>
        _, rest = field_.split(":", 1)
        prov, key = rest.split(".", 1) if "." in rest else (rest, "")
        return _safe_get(risk.get("signals", {}).get(prov, {}), key)
    return _safe_get(device, field_)


def _cmp(a, op, b):
    try:
        if op == "gte": return float(a) >= float(b)
        if op == "gt":  return float(a) > float(b)
        if op == "lte": return float(a) <= float(b)
        if op == "lt":  return float(a) < float(b)
        if op == "eq":  return a == b
        if op == "ne":  return a != b
        if op == "in":  return a in (b or [])
        if op == "contains": return b in (a or "")
    except Exception:
        return False
    return False
