"""SOAR playbook engine (Security Orchestration, Automation & Response).

Redisenado inspirado en motores de reglas de la industria
(cloud-custodian / StackStorm):

* Una condicion ya no es una lambda hardcodeada, sino una **especificacion
  declarativa** compuesta por operadores reutilizables (eq, gt, in, contains,
  glob, regex, exists...) y combinadores logicos `all` (AND) / `any` (OR) /
  `not`. Es legible, serializable a JSON/YAML y validable.
* Cada playbook se **valida** al cargar (`SOARPlaybook.validate()`), asi un
  playbook mal formado falla limpio en arranque en vez de romper el ciclo.
* Las condiciones anotan que campos matchearon (auditoria, estilo c7n
  `c7n:MatchedFilters`).

Pure y TDD-friendly: las condiciones son callables/plain data; nada toca red.
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# --------------------------------------------------------------------------
# Operadores reutilizables (estilo cloud-custodian OPERATORS)
# --------------------------------------------------------------------------
def _as_num(v: Any):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


_OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": lambda a, b: a == b,
    "equal": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "not_equal": lambda a, b: a != b,
    "gt": lambda a, b: (x := _as_num(a)) is not None and (y := _as_num(b)) is not None and x > y,
    "greater_than": lambda a, b: (x := _as_num(a)) is not None and (y := _as_num(b)) is not None and x > y,
    "ge": lambda a, b: (x := _as_num(a)) is not None and (y := _as_num(b)) is not None and x >= y,
    "gte": lambda a, b: (x := _as_num(a)) is not None and (y := _as_num(b)) is not None and x >= y,
    "lt": lambda a, b: (x := _as_num(a)) is not None and (y := _as_num(b)) is not None and x < y,
    "less_than": lambda a, b: (x := _as_num(a)) is not None and (y := _as_num(b)) is not None and x < y,
    "le": lambda a, b: (x := _as_num(a)) is not None and (y := _as_num(b)) is not None and x <= y,
    "lte": lambda a, b: (x := _as_num(a)) is not None and (y := _as_num(b)) is not None and x <= y,
    "in": lambda a, b: a in b if isinstance(b, (list, tuple, set, dict)) else False,
    "not_in": lambda a, b: a not in b if isinstance(b, (list, tuple, set, dict)) else True,
    "contains": lambda a, b: b in a if isinstance(a, (list, tuple, str)) else False,
    "glob": lambda a, b: fnmatch.fnmatch(str(a), str(b)),
    "regex": lambda a, b: bool(re.match(str(b), str(a), flags=re.IGNORECASE)),
    "exists": lambda a, b: (a is not None) == bool(b),
    "truthy": lambda a, b: bool(a) == bool(b),
}


def _resolve_field(device: dict, expr: str):
    """Resuelve una ruta tipo 'apps[].max_cve_severity' sobre el dispositivo.

    Soporta proyeccion `[]` (devuelve lista de valores) y acceso anidado con
    '.'. Si la ruta no existe devuelve None.
    """
    if not expr:
        return None
    cur: Any = device
    for part in expr.split("."):
        if part.endswith("[]"):
            key = part[:-2]
            if not isinstance(cur, dict) or key not in cur:
                return None
            items = cur[key]
            if not isinstance(items, list):
                return None
            # proyectamos el resto sobre cada elemento
            rest = expr.split(".", 1)[1] if "." in expr.split("[]", 1)[1] else ""
            # reconstruimos la sub-expresion restante
            sub = expr[expr.index("[]") + 2:].lstrip(".")
            if not sub:
                return [i for i in items]
            out = []
            for it in items:
                v = _resolve_field(it, sub) if isinstance(it, dict) else None
                if v is not None:
                    out.append(v)
            return out
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def compile_condition(spec: Any) -> Callable[[dict], tuple[bool, list]]:
    """Compila una especificacion declarativa en (device) -> (match, campos).

    Formatos:
      {"field": "x.y", "op": "in", "value": [...]}
      {"all": [spec, spec, ...]}   # AND
      {"any": [spec, spec, ...]}   # OR
      {"not": spec}                # NOT
      callable                     # compatibilidad legacy
    Devuelve (matched, lista_de_campos_que_matchearon).
    """
    if callable(spec):
        def legacy(d, ctx=None):
            try:
                return (bool(spec(d, ctx or {})), [])
            except Exception:
                return (False, [])
        return legacy

    if isinstance(spec, dict):
        if "all" in spec:
            subs = [compile_condition(s) for s in spec["all"]]
            def allf(d, ctx=None):
                matched = True
                fields: list = []
                for s in subs:
                    m, f = s(d, ctx)
                    if not m:
                        matched = False
                    fields.extend(f)
                return (matched, fields)
            return allf
        if "any" in spec:
            subs = [compile_condition(s) for s in spec["any"]]
            def anyf(d, ctx=None):
                matched = False
                fields: list = []
                for s in subs:
                    m, f = s(d, ctx)
                    if m:
                        matched = True
                    fields.extend(f)
                return (matched, fields)
            return anyf
        if "not" in spec:
            sub = compile_condition(spec["not"])
            def notf(d, ctx=None):
                m, f = sub(d, ctx)
                return (not m, f)
            return notf
        # hoja: field/op/value
        field_expr = spec.get("field")
        op = spec.get("op", "eq")
        val = spec.get("value")
        fn = _OPERATORS.get(op)
        if fn is None:
            raise ValueError(f"operador SOAR desconocido: {op}")
        def leaf(d, ctx=None):
            actual = _resolve_field(d, field_expr or "")
            # una proyeccion devuelve lista: matchea si CUALQUIERA cumple
            if isinstance(actual, list):
                ok = any(fn(x, val) for x in actual)
            else:
                ok = fn(actual, val)
            return (bool(ok), [field_expr] if ok else [])
        return leaf

    raise ValueError(f"especificacion de condicion SOAR no valida: {spec!r}")


# --------------------------------------------------------------------------
# Playbook
# --------------------------------------------------------------------------
@dataclass
class SOARPlaybook:
    id: str
    name: str
    condition: Any  # callable legacy O especificacion declarativa
    actions: list[dict] = field(default_factory=list)
    description: str = ""
    enabled: bool = True
    severity_min: str = "low"  # minima severidad del dispositivo para ser elegible

    def __post_init__(self):
        # pre-compila la condicion declarativa; si falla, se marca en validate()
        try:
            self._compiled = compile_condition(self.condition)
        except Exception:
            self._compiled = None

    def validate(self) -> list[str]:
        """Devuelve lista de errores (vacía si todo OK)."""
        errs: list[str] = []
        if not self.id:
            errs.append("playbook sin id")
        if not self.name:
            errs.append(f"{self.id}: nombre vacio")
        if not self.actions:
            errs.append(f"{self.id}: sin acciones")
        for a in self.actions:
            if not isinstance(a, dict) or not a.get("action"):
                errs.append(f"{self.id}: accion mal formada {a!r}")
        try:
            compile_condition(self.condition)
        except Exception as e:
            errs.append(f"{self.id}: condicion invalida: {e}")
        return errs

    def matches(self, device: dict, ctx: dict) -> tuple[bool, list]:
        if self._compiled is None:
            return (False, [])  # playbook no compilable: lo detecta validate()
        try:
            return self._compiled(device, ctx)
        except Exception as exc:
            cb = ctx.get("on_error")
            if callable(cb):
                cb(self.id, exc)
            return (False, [])


def evaluate_soar(device: dict, playbooks: list[SOARPlaybook], ctx: dict) -> list[dict]:
    """Devuelve las ejecuciones de playbook que matchean este dispositivo.

    Cada resultado: {playbook_id, name, actions, severity, matched_fields}.
    Nunca lanza: un playbook roto se salta (auditado via ctx.on_error).
    """
    results: list[dict] = []
    for pb in playbooks:
        if not pb.enabled:
            continue
        try:
            matched, fields = pb.matches(device, ctx)
        except Exception:
            matched = False
            fields = []
        if matched:
            results.append({
                "playbook_id": pb.id,
                "name": pb.name,
                "actions": pb.actions,
                "severity": _max_severity(device),
                "matched_fields": fields,
            })
    return results


def _max_severity(device: dict) -> str:
    """Mayor severidad relevante (CVEs de apps o nivel de riesgo)."""
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    best = "low"
    for a in (device.get("apps") or []):
        s = (a.get("max_cve_severity") or "low")
        if order.get(s, 0) > order.get(best, 0):
            best = s
    lvl = (device.get("risk_level") or device.get("level") or "low")
    if order.get(lvl, 0) > order.get(best, 0):
        best = lvl
    return best


# ---- playbooks por defecto (frontline UEM security ops) -------------------
# Declarativos (estilo cloud-custodian), no lambdas.
DEFAULT_PLAYBOOKS: list[SOARPlaybook] = [
    SOARPlaybook(
        id="soar-cve-critical",
        name="App con CVE critico instalada",
        description="Notifica al SOC y marca para desinstalacion de la app vulnerable.",
        condition={"field": "apps[].max_cve_severity", "op": "eq", "value": "critical"},
        actions=[
            {"action": "notify", "params": {"channel": "soc", "priority": "high",
                                            "message": "App con CVE critico detectada en dispositivo"}},
            {"action": "flag_app", "params": {"reason": "cve_critical"}},
        ],
    ),
    SOARPlaybook(
        id="soar-cve-outside",
        name="CVE alto + fuera de geovalla",
        description="Dispositivo con app vulnerable fuera de perimetro: localizar y bloquear.",
        condition={"all": [
            {"field": "apps[].max_cve_severity", "op": "in", "value": ["critical", "high"]},
            {"field": "fence_state", "op": "eq", "value": "outside"},
        ]},
        actions=[
            {"action": "locate", "params": {}},
            {"action": "lock", "params": {"reason": "cve_outside_perimeter"}},
            {"action": "notify", "params": {"channel": "soc", "priority": "high"}},
        ],
    ),
    SOARPlaybook(
        id="soar-rooted-outside",
        name="No conforme + fuera de perimetro",
        description="Dispositivo no conforme fuera de geovalla: bloqueo inmediato.",
        condition={"all": [
            {"field": "compliant", "op": "eq", "value": False},
            {"field": "fence_state", "op": "eq", "value": "outside"},
        ]},
        actions=[
            {"action": "lock", "params": {"reason": "noncompliant_outside"}},
            {"action": "notify", "params": {"channel": "soc"}},
        ],
    ),
    SOARPlaybook(
        id="soar-cve-epss-high",
        name="CVE con alta probabilidad de exploit (EPSS)",
        description="App con EPSS alto: escala prioridad de respuesta del SOC.",
        condition={"field": "apps[].epss_max", "op": "gt", "value": 0.5},
        actions=[
            {"action": "notify", "params": {"channel": "soc", "priority": "critical",
                                            "message": "CVE con EPSS>0.5: exploit activo probable"}},
        ],
    ),
]


def validate_playbooks(playbooks: list[SOARPlaybook]) -> list[str]:
    """Valida todos los playbooks; devuelve errores concatenados."""
    errs: list[str] = []
    for pb in playbooks:
        errs.extend(pb.validate())
    return errs
