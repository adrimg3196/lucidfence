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
    encryption = device.get("encryption_enabled")
    return {
        "compliant": bool(device.get("compliant")),
        "rooted": bool(device.get("rooted", False)),
        # Unknown posture is not evidence of disabled encryption.
        "encryption": True if encryption is None else bool(encryption),
        "os_outdated": bool(device.get("os_outdated", False)),
    }


# Normalización de estados de componente de hardware (DDM OS 27). Solo se
# considera degradado lo reportado EXPLÍCITAMENTE como tal: False o un string
# reconocido. Un string desconocido/valor raro es "desconocido" y NO penaliza.
_HW_DEGRADED_WORDS = {"degraded", "failed", "error"}
_HW_HEALTHY_WORDS = {"ok", "healthy", "normal"}


def _hardware_degraded_components(hardware_health) -> list:
    """Claves del dict hardware_health reportadas explícitamente degradadas.

    Readback honesto: None/no-dict/dict vacío -> []. Valores no interpretables
    (ints, listas, strings fuera del vocabulario) se ignoran en silencio —
    desconocido nunca inventa riesgo.
    """
    if not isinstance(hardware_health, dict):
        return []
    degraded = []
    for component, value in hardware_health.items():
        if not isinstance(component, str):
            continue
        if value is False:
            degraded.append(component)
        elif isinstance(value, str) and value.strip().lower() in _HW_DEGRADED_WORDS:
            degraded.append(component)
        # True / "ok"/"healthy"/"normal" = sano; cualquier otra cosa = desconocido.
    return degraded


@register_signal("device_posture")
def sig_device_posture(device, ctx):
    """Señales de posture del endpoint (inspirado en Fleet/osquery):
    disco casi lleno, batería crítica, SO sin parchear, sin cifrado.
    El Risk Engine las usa para penalizar el score de forma explicable."""
    free = device.get("storage_free_gb")
    total = device.get("storage_total_gb")
    battery = device.get("battery_level")
    os_ver = (device.get("os_version") or "").lower()
    encryption_value = device.get("encryption_enabled")
    encryption = True if encryption_value is None else bool(encryption_value)

    disk_low = False
    if free is not None and total:
        try:
            disk_low = (float(free) / float(total)) < 0.10  # <10% libre
        except (TypeError, ValueError):
            disk_low = False
    battery_critical = battery is not None and float(battery) <= 15
    # Heurística de SO sin parchear: versiones "antiguas" conocidas por plataforma.
    os_unpatched = any(tok in os_ver for tok in ("android 12", "android 11", "ios 15", "windows 10", "windows 10 pro", "win10"))

    # Lockdown Mode (Apple OS 27 DDM status item, WWDC 2026): readback de la UEM.
    # SOLO es "off" cuando la UEM lo reporta explícitamente False. None/ausente
    # (el caso común: la UEM aún no lo expone) NO penaliza — nunca se inventa
    # riesgo a partir de un dato desconocido.
    lockdown_mode_off = device.get("lockdown_mode") is False
    # Enrolamiento sin supervisión (Apple OS 27 enrollment-type status item):
    # SOLO es "unsupervised" cuando la UEM reporta supervised explícitamente
    # False. None/ausente NO penaliza — desconocido nunca inventa riesgo.
    unsupervised = device.get("supervised") is False
    # Salud de hardware (Apple OS 27 hardware-health status items, WWDC 2026):
    # SOLO degradado cuando algún componente lo reporta explícitamente
    # (False o "degraded"/"failed"/"error"). None/dict vacío/valores raros
    # NO penalizan — desconocido nunca inventa riesgo.
    hw_degraded = _hardware_degraded_components(device.get("hardware_health"))

    return {
        "disk_low": disk_low,
        "battery_critical": battery_critical,
        "os_unpatched": os_unpatched,
        "encryption_off": not encryption,
        "lockdown_mode_off": lockdown_mode_off,
        "unsupervised": unsupervised,
        "hardware_degraded": bool(hw_degraded),
        "hardware_degraded_components": hw_degraded,
        "osquery_config_invalid": device.get("osquery_config_valid") is False,
    }


@register_signal("location_integrity")
def sig_location_integrity(device, ctx):
    """Anti-spoofing: verosimilitud del report de ubicación (ver
    location_integrity.py). El engine calcula los checks contra el último
    estado persistido y los adjunta al device; aquí solo se exponen como
    señal explicable para el score."""
    li = device.get("location_integrity") or {}
    return {
        "suspicious": bool(li.get("suspicious")),
        "checks": list(li.get("checks") or []),
        "speed_kmh": li.get("speed_kmh"),
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


# Vocabulario que el motor entiende de verdad: ops de _cmp() y acciones que
# los adapters saben ejecutar (APPLIVERY_ACTIONS + retire de policy_replay).
VALID_OPS = {"gte", "gt", "lte", "lt", "eq", "ne", "in", "contains"}
VALID_POLICY_ACTIONS = {
    "lock", "wipe", "message", "locate", "reboot", "clear_passcode", "notify", "custom", "retire"
}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}


def validate_policies(raw: Any) -> list[str]:
    """Espejo de fences.validate_fences para policies.json (lista vacía == OK).

    Opera sobre el JSON parseado, no sobre Policy: load_policies() rellena
    defaults y ocultaría los campos rotos. Cada problema lleva el id del
    objeto para que el error sea accionable:
      - fichero que no es lista / objeto que no es dict / id ausente o duplicado
      - `when` vacío o con condiciones sin field/op válido/value
      - acciones fuera del catálogo que los adapters ejecutan
      - severidad fuera de low|medium|high|critical
    """
    if not isinstance(raw, list):
        return ["el fichero debe ser una LISTA de políticas"]
    problems: list[str] = []
    seen: set[str] = set()
    for i, p in enumerate(raw):
        if not isinstance(p, dict):
            problems.append(f"objeto #{i}: debe ser un objeto, no {type(p).__name__}")
            continue
        pid = str(p.get("id") or f"objeto #{i}")
        if not p.get("id"):
            problems.append(f"{pid}: falta 'id'")
        elif p["id"] in seen:
            problems.append(f"duplicate policy id: {pid}")
        else:
            seen.add(p["id"])
        when = p.get("when")
        if not isinstance(when, list) or not when:
            problems.append(f"{pid}: 'when' debe ser una lista no vacía de condiciones")
        else:
            for j, c in enumerate(when):
                if not isinstance(c, dict) or not c.get("field"):
                    problems.append(f"{pid}: condición #{j} sin 'field'")
                    continue
                op = c.get("op", "gte")
                if op not in VALID_OPS:
                    problems.append(
                        f"{pid}: condición '{c['field']}' con op desconocido {op!r}"
                        f" (usa {'|'.join(sorted(VALID_OPS))})")
                if "value" not in c:
                    problems.append(f"{pid}: condición '{c['field']}' sin 'value'")
        actions = p.get("actions", [])
        if not isinstance(actions, list):
            problems.append(f"{pid}: 'actions' debe ser una lista")
        else:
            for a in actions:
                name = a.get("action") if isinstance(a, dict) else None
                if name not in VALID_POLICY_ACTIONS:
                    problems.append(
                        f"{pid}: acción desconocida {name!r}"
                        f" (usa {'|'.join(sorted(VALID_POLICY_ACTIONS))})")
        sev = p.get("severity", "medium")
        if sev not in VALID_SEVERITIES:
            problems.append(f"{pid}: severidad {sev!r} inválida (low|medium|high|critical)")
    return problems


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
        if posture.get("os_unpatched") and not signals.get("device_health", {}).get("os_outdated"):
            score += 12; reasons.append("SO sin parchear de seguridad")
        if posture.get("encryption_off"):
            score += 15; reasons.append("almacenamiento sin cifrar")
        if posture.get("lockdown_mode_off"):
            score += 10; reasons.append("Lockdown Mode desactivado")
        if posture.get("unsupervised"):
            score += 10; reasons.append("dispositivo sin supervisión (enrolamiento personal)")
        if posture.get("hardware_degraded"):
            comps = ", ".join(posture.get("hardware_degraded_components") or [])
            score += 10; reasons.append(f"salud de hardware degradada ({comps})")
        if posture.get("osquery_config_invalid"):
            score += 8; reasons.append("configuración de osquery no válida")

        # Anti-spoofing: un report inverosímil convierte el "dónde" en no
        # confiable — y todo lo demás (geocerca, ruta, turno) cuelga del dónde.
        li_checks = signals.get("location_integrity", {}).get("checks") or []
        if "impossible_speed" in li_checks:
            kmh = signals.get("location_integrity", {}).get("speed_kmh") or 0
            score += 30
            reasons.append(f"velocidad imposible entre reportes ({int(kmh)} km/h): posible spoofing de ubicación")
        if "country_flip_without_movement" in li_checks:
            score += 15
            reasons.append("país declarado cambió sin movimiento acorde: metadatos de ubicación incoherentes")
        if "accuracy_invalid" in li_checks:
            score += 8
            reasons.append("precisión GPS inválida (accuracy ≤ 0): report no fiable")
        if "accuracy_too_perfect" in li_checks:
            score += 8
            reasons.append("precisión imposible para geolocalización por IP: campo falseado")

        if signals.get("time_of_day", {}).get("off_hours"):
            score += 10; reasons.append("fuera de horario laboral")
        if signals.get("shift_match", {}).get("shift_known") and not signals.get("shift_match", {}).get("shift_match"):
            score += 20; reasons.append("dispositivo fuera de su turno asignado")

        zr = signals.get("zone_risk", {}).get("zone_risk", 0.0) or 0.0
        if zr:
            score += float(zr) * 20; reasons.append(f"zona de riesgo elevado ({zr})")

        # CVE risk from device apps (external vulnerability signal) — moat "riesgo compuesto"
        max_cve = 0.0
        for app in (device.get("apps") or []):
            cr = app.get("cve_risk") or app.get("max_cve_severity_score") or 0.0
            try:
                cr = float(cr)
            except (TypeError, ValueError):
                cr = 0.0
            if cr > max_cve:
                max_cve = cr
        if max_cve:
            score += min(40.0, max_cve * 0.4)
            reasons.append(f"apps con CVE de riesgo ({int(max_cve)}/100)")

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
    if field_ == "hardware_degraded":
        # Señal derivada (no vive en el device dict, a diferencia de
        # supervised/lockdown_mode): se resuelve desde la señal de postura ya
        # calculada, con fallback a derivarla del propio device si el caller
        # pasó un `risk` sin señales. Desconocido -> False (no casa eq true).
        posture = (risk.get("signals") or {}).get("device_posture")
        if isinstance(posture, dict) and "hardware_degraded" in posture:
            return posture["hardware_degraded"]
        return bool(_hardware_degraded_components(device.get("hardware_health")))
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
