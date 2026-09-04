"""Auditor de mínimo privilegio de las credenciales UEM (backlog §16).

LucidFence es el complemento, y debe ser el eslabón MENOS peligroso de la
cadena: si el tenant está en modo observe, un token que puede *wipear* no
aporta nada al producto y sí añade superficie de ataque. Este módulo compara,
por proveedor, lo que la credencial DECLARA poder hacer contra lo que el modo
de enforcement actual necesita de verdad, y nombra el exceso.

Función pura: cero red, cero disco, cero escritura. No recibe —ni puede
recibir— la credencial: solo el nombre del proveedor y los scopes declarados.

DE DÓNDE SALEN LOS SCOPES (invariante de honestidad):
    Aquí NO hay tabla de scopes de Intune/Jamf/Fleet. Inventarla sería afirmar
    permisos que nadie ha verificado, justo el pecado que este auditor existe
    para denunciar. Qué scopes tiene el token, y qué concede cada uno, es DATO
    DE ENTRADA: lo declara el operador al conectar el adapter (o lo reporta el
    UEM si lo expone). Un scope que no dice qué concede no se interpreta: se
    lista como no clasificado.

TRES ESTADOS, NUNCA DOS (misma regla que `devices_verifiable` en
second_opinion.py):
    - ``correcto``      auditado: sus scopes son los que el modo necesita.
    - ``exceso``        auditado: sobra permiso, con QUÉ sobra y POR QUÉ.
    - ``no_auditable``  no sabemos qué puede el token (el UEM no lo expone, no
                        hay credencial, o el scope no declara su concesión).
      NUNCA se presenta como correcto ni como excesivo.
El resumen publica `providers_auditables` para que "0 excesos" no pueda leerse
como "todo bien" sobre un registro que nadie ha podido auditar.
"""
from __future__ import annotations

from lucidfence.core.adapters import VALID_ACTIONS
from lucidfence.core.adapters.capabilities import capability_for

#: Concesión de solo lectura del inventario. LucidFence la necesita en TODOS
#: los modos (leer del UEM es el producto entero), así que nunca es exceso.
READ_GRANT = "read"

#: Vocabulario que sabemos interpretar: las acciones que el producto ya conoce
#: (contrato de MDMAdapter) más la lectura. Cualquier otra palabra es un scope
#: que no sabemos traducir a riesgo — y decirlo es más honesto que adivinarlo.
_KNOWN_GRANTS = frozenset(VALID_ACTIONS) | {READ_GRANT}

_UNDECLARED = "(no declara qué concede)"


def normalize_declared_scopes(raw) -> list[dict]:
    """Normaliza los scopes declarados al conectar un adapter, para persistirlos.

    Se queda con lo que tiene forma auditable — ``{"id": str, "grants": [str]}``
    — y descarta el resto. Nunca lanza: un payload basura deja al proveedor sin
    scopes, y sin scopes el auditor lo marca *no auditable* (que es la verdad),
    en vez de fabricar una declaración que nadie hizo.
    """
    out: list[dict] = []
    for item in raw if isinstance(raw, (list, tuple)) else []:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("id") or "").strip()[:200]
        if not sid:
            continue
        grants = item.get("grants")
        entry: dict = {"id": sid}
        if isinstance(grants, (list, tuple)):
            entry["grants"] = [str(g).strip()[:64] for g in grants if str(g).strip()]
        out.append(entry)
    return out


def _needed_actions(provider_name: str, enforcement: dict) -> frozenset[str]:
    """Acciones que LucidFence PUEDE ejecutar en vivo hoy, en este tenant.

    Es el listón contra el que se mide el token, y sale del runtime real
    (`Engine.enforcement_status()`), nunca de una preferencia del auditor.
    """
    mode = str((enforcement or {}).get("mode") or "observe").strip().lower()
    if mode != "enforce":
        # observe: el engine fuerza dry_run, no sale NI UNA acción en vivo.
        # Por definición, cualquier permiso de escritura sobra.
        return frozenset()
    cap = capability_for(provider_name)
    # Un UEM sin matriz declarada conserva el fallback legacy del registro de
    # adapters (todas las VALID_ACTIONS): no le atribuimos menos capacidad de
    # la que puede tener, porque eso inflaría el exceso con falsos positivos.
    acts = frozenset(cap.actions) if cap is not None else frozenset(VALID_ACTIONS)
    live = (enforcement or {}).get("live_actions")
    if isinstance(live, (list, tuple, set)):  # "all" (str) = sin acotar
        acts &= {str(a) for a in live}
    # wipe es la doble llave: sin allow_wipe explícito jamás sale en vivo, así
    # que el permiso de wipe sobra aunque el tenant esté en enforce.
    if not (enforcement or {}).get("allow_wipe"):
        acts -= {"wipe"}
    return acts


def _parse_scope(raw) -> tuple[str, list[str], list[str]]:
    """(id, grants reconocidos, grants no interpretables) de un scope declarado."""
    if isinstance(raw, str) and raw.strip():
        # Texto suelto: sabemos que el scope existe, no qué permite. Traducir
        # "DeviceManagementManagedDevices.PrivilegedOperations.All" a acciones
        # sería inventarse la tabla de scopes del UEM.
        return raw.strip(), [], [_UNDECLARED]
    if not isinstance(raw, dict):
        return "(scope ilegible)", [], [_UNDECLARED]
    sid = str(raw.get("id") or "").strip() or "(scope sin id)"
    grants = raw.get("grants")
    if not isinstance(grants, (list, tuple)):
        return sid, [], [_UNDECLARED]
    known, unknown = [], []
    for item in grants:
        text = str(item).strip()
        if not text:
            continue
        (known if text in _KNOWN_GRANTS else unknown).append(text)
    return sid, known, unknown


def _why(surplus: list[str], provider_name: str, enforcement: dict,
         needed: frozenset[str]) -> str:
    """Por qué ESE permiso es peligroso en ESTE modo, en una frase accionable."""
    puede = ("puede BORRAR el dispositivo (wipe: irreversible)"
             if "wipe" in surplus else "puede ejecutar acciones sobre el dispositivo")
    acciones = ", ".join(surplus)
    mode = str((enforcement or {}).get("mode") or "observe").strip().lower()
    if mode != "enforce":
        return (f"El token {puede} ({acciones}) y el tenant está en modo observe: "
                "LucidFence no ejecuta NINGUNA acción en vivo en este modo, así "
                "que ese permiso solo añade superficie de ataque. Recórtalo a "
                "solo lectura.")
    cap = capability_for(provider_name)
    motivos = []
    for action in surplus:
        if cap is not None and action not in cap.actions:
            motivos.append(f"{action} (LucidFence no la ejecuta contra este UEM)")
        elif action == "wipe":
            motivos.append("wipe (doble llave cerrada: allow_wipe=false)")
        else:
            motivos.append(f"{action} (fuera de las live_actions del tenant)")
    return (f"El token {puede} ({acciones}), pero en el enforcement actual esas "
            "acciones no salen en vivo: " + "; ".join(motivos) +
            f". Lo que sí se usa: {', '.join(sorted(needed)) or 'nada'}.")


def _audit_provider(provider: dict, enforcement: dict) -> dict:
    name = str(provider.get("name") or "")
    needed = _needed_actions(name, enforcement)
    raw_scopes = provider.get("scopes")
    raw_scopes = list(raw_scopes) if isinstance(raw_scopes, (list, tuple)) else []
    out = {
        "provider": name,
        "scopes_declarados": [],
        "exceso": [],
        "scopes_recomendados": [],
        "scopes_sin_clasificar": [],
        # El mínimo que la documentación del repo ya exige para este UEM
        # (`min_permission` del catálogo de conectores). Llega como dato; este
        # módulo no escribe permisos de ningún UEM real.
        "min_permission_documentada": provider.get("min_permission") or None,
    }
    if not raw_scopes:
        out["veredicto"] = "no_auditable"
        out["motivo"] = ("sin credencial configurada: no hay token que auditar"
                         if provider.get("configured") is False else
                         "el UEM no expone los scopes de su credencial y nadie "
                         "los ha declarado al conectar el adapter")
        return out

    for raw in raw_scopes:
        sid, known, unknown = _parse_scope(raw)
        out["scopes_declarados"].append(sid)
        if unknown:
            out["scopes_sin_clasificar"].append(
                {"scope": sid, "grants_no_reconocidos": unknown})
        surplus = sorted(g for g in known if g != READ_GRANT and g not in needed)
        if surplus:
            out["exceso"].append({
                "scope": sid,
                "grants": surplus,
                # wipe es la única acción irreversible del contrato: su exceso
                # no es del mismo orden que el de un `message`.
                "severity": "critical" if "wipe" in surplus else "high",
                "why": _why(surplus, name, enforcement, needed),
            })
        if READ_GRANT in known or any(g in needed for g in known):
            out["scopes_recomendados"].append(sid)

    if out["exceso"]:
        # Un exceso demostrado manda sobre lo no clasificado: el hallazgo es
        # real aunque queden scopes sin interpretar.
        out["veredicto"] = "exceso"
    elif out["scopes_sin_clasificar"]:
        out["veredicto"] = "no_auditable"
        out["motivo"] = ("hay scopes que no declaran qué conceden: no se puede "
                         "afirmar que el token esté acotado")
    else:
        out["veredicto"] = "correcto"
    return out


def least_privilege_report(providers: list[dict], enforcement: dict) -> dict:
    """Auditoría de mínimo privilegio de los adapters conectados de un tenant.

    `providers` son dicts NO secretos: ``{"name", "scopes", "configured",
    "min_permission"}``. La credencial jamás entra aquí. `enforcement` es el
    estado vivo de `Engine.enforcement_status()`.
    """
    rows = [_audit_provider(p, enforcement)
            for p in (providers or []) if isinstance(p, dict) and p.get("name")]
    con_exceso = [r for r in rows if r["veredicto"] == "exceso"]
    correctos = [r for r in rows if r["veredicto"] == "correcto"]
    no_auditables = [r for r in rows if r["veredicto"] == "no_auditable"]
    enf = enforcement or {}
    return {
        "enforcement": {
            "mode": str(enf.get("mode") or "observe").strip().lower(),
            "live_actions": enf.get("live_actions"),
            "allow_wipe": bool(enf.get("allow_wipe")),
        },
        "providers": rows,
        "resumen": {
            "providers_total": len(rows),
            # Sin esto, "0 excesos" sobre un registro no auditable se leería
            # como "todo bien". Es el mismo denominador honesto de
            # devices_verifiable en second_opinion.py.
            "providers_auditables": len(con_exceso) + len(correctos),
            "providers_no_auditables": len(no_auditables),
            "providers_con_exceso": len(con_exceso),
            "providers_correctos": len(correctos),
            "scopes_excesivos": sum(len(r["exceso"]) for r in rows),
        },
    }
