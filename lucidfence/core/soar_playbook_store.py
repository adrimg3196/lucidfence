"""Persistencia de playbooks SOAR por tenant (local-first, sin red).

El motor SOAR ya existe (core/soar.py) con condiciones declarativas y los
4 DEFAULT_PLAYBOOKS. Este módulo añade la capa de producto requerida en REQ §5:
el cliente puede crear/editar/activar su propio playbook desde la UI, con
validación en caliente, sin tocar código. Las defaults del producto siguen
viniendo del código; las del tenant se guardan en su directorio (0600) y se
fusionan en tiempo de ciclo. Nunca se exfiltran credenciales: aquí solo viven
definiciones de playbook (condición + acciones), no secretos.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from lucidfence.core.soar import SOARPlaybook, validate_playbooks

_PLAYBOOKS_FILENAME = "soar_playbooks.json"


@dataclass
class TenantPlaybookStore:
    """Carga/guarda playbooks de un tenant en <data_dir>/soar_playbooks.json.

    Los playbooks del tenant se combinan con ``DEFAULT_PLAYBOOKS`` en el engine.
    Cualquier playbook roto se detecta en ``validate()`` y se salta (auditado),
    nunca rompe el ciclo (contrato de core/soar.py).
    """

    data_dir: str
    builtin: list[SOARPlaybook] = field(default_factory=list)

    # ---- rutas ----------------------------------------------------------
    @property
    def path(self) -> Path:
        return Path(self.data_dir) / _PLAYBOOKS_FILENAME

    # ---- lectura --------------------------------------------------------
    def load(self) -> list[SOARPlaybook]:
        """Devuelve los playbooks del tenant (no los builtin). Vacío si no hay."""
        p = self.path
        if not p.exists():
            return []
        try:
            raw = json.loads(p.read_text("utf-8"))
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        out: list[SOARPlaybook] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            pb = _from_dict(item)
            if pb is not None:
                out.append(pb)
        return out

    def all_playbooks(self) -> list[SOARPlaybook]:
        """Builtin del producto + los del tenant, en un solo lista para evaluar."""
        return list(self.builtin) + self.load()

    def errors(self) -> list[str]:
        """Validación en caliente de los playbooks del tenant (REQ §5)."""
        return validate_playbooks(self.load())

    def get(self, playbook_id: str) -> SOARPlaybook | None:
        for pb in self.load():
            if pb.id == playbook_id:
                return pb
        return None

    # ---- escritura -----------------------------------------------------
    def _write(self, playbooks: list[SOARPlaybook]) -> None:
        p = self.path
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = [_to_dict(pb) for pb in playbooks]
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), "utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)

    def upsert(self, spec: dict) -> SOARPlaybook:
        """Crea o reemplaza un playbook del tenant. Valida antes de escribir.

        ``spec``: {id, name, condition, actions, enabled?, severity_min?, description?}.
        Lanza ValueError si la definición no valida (validación en caliente).
        """
        pb = _from_dict(spec)
        if pb is None:
            raise ValueError("playbook mal formado (faltan id/name/condition/actions)")
        errs = pb.validate()
        if errs:
            raise ValueError("; ".join(errs))
        existing = self.load()
        replaced = False
        for i, item in enumerate(existing):
            if item.id == pb.id:
                existing[i] = pb
                replaced = True
                break
        if not replaced:
            existing.append(pb)
        self._write(existing)
        return pb

    def set_enabled(self, playbook_id: str, enabled: bool) -> bool:
        existing = self.load()
        for i, item in enumerate(existing):
            if item.id == playbook_id:
                pb = SOARPlaybook(
                    id=item.id, name=item.name, condition=item.condition,
                    actions=item.actions, description=item.description,
                    enabled=enabled, severity_min=item.severity_min,
                )
                existing[i] = pb
                self._write(existing)
                return True
        return False

    def delete(self, playbook_id: str) -> bool:
        existing = self.load()
        filtered = [item for item in existing if item.id != playbook_id]
        if len(filtered) == len(existing):
            return False
        self._write(filtered)
        return True


# ---- serialización (sole id/name/condition/actions; sin secretos) --------
def _to_dict(pb: SOARPlaybook) -> dict:
    return {
        "id": pb.id,
        "name": pb.name,
        "description": pb.description,
        "enabled": pb.enabled,
        "severity_min": pb.severity_min,
        "condition": pb.condition,
        "actions": pb.actions,
    }


def _from_dict(item: dict) -> SOARPlaybook | None:
    pid = item.get("id")
    name = item.get("name")
    condition = item.get("condition")
    actions = item.get("actions")
    if not pid or not name or condition is None or not isinstance(actions, list):
        return None
    return SOARPlaybook(
        id=str(pid),
        name=str(name),
        condition=condition,
        actions=actions,
        description=str(item.get("description", "")),
        enabled=bool(item.get("enabled", True)),
        severity_min=str(item.get("severity_min", "low")),
    )
