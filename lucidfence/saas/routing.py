"""Registro declarativo de rutas API — el seam del dispatch HTTP (SD-1 paso 1).

Vocabulario (skill codebase-design): este módulo es un **módulo profundo** cuyo
**seam** separa a los autores de endpoints del ritual HTTP completo. La
**interfaz** que un autor debe conocer es mínima — un decorador y una función:

    @api_route("GET", "/api/coverage", cap="device:read")
    def _coverage(ctx):
        return coverage_report(...)            # -> payload  (o (payload, status))

Detrás del seam vive TODA la **implementación** del ritual que antes se copiaba
en cada rama `if route == …` de `saas_server.py`: lookup por (método, ruta),
chequeo de capability RBAC con el 403 canónico ``{"error": "sin permiso"}``,
desempaquetado del resultado y envío JSON. La sesión, la organización activa y
el Engine del tenant los resuelve una sola vez el dispatcher legacy (require /
engine_for) y llegan empaquetados en :class:`Ctx` — el autor no repite nada.

Invariante de seguridad (estructural, no por convención): **toda ruta
registrada declara una capability no vacía**. ``cap`` es keyword-only y sin
default; un valor vacío levanta ``ValueError`` en el registro, no en producción.

Test de borrado: si este módulo se borra, el ritual (cap-check + 403 + envío
JSON) reaparece copiado en cada ruta migrada — se gana su sitio. Dos
**adapters** cruzan hoy el seam: el `Handler` HTTP real de `saas_server.py`
(producción) y el ctx fake de `tests/test_route_registry.py` — **la interfaz es
la superficie de test**. Depende solo de stdlib + `lucidfence.saas.auth`.

Este módulo no guarda estado global: la instancia de :class:`RouteRegistry`
vive en quien la usa (`saas_server.py` crea la suya y expone su decorador como
`api_route`). Así, re-ejecutar el módulo del servidor (tests que lo cargan por
path) nunca choca con registros de una ejecución anterior.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from .auth import AuthStore

# 403 canónico, byte-idéntico al de la cadena legacy de saas_server.py.
DENIED = {"error": "sin permiso"}


@dataclass(frozen=True)
class Ctx:
    """Todo lo que el ritual legacy ya resolvía antes de cada rama `if`.

    Empaquetado para que la firma del handler sea un solo parámetro.
    """

    http: Any    # BaseHTTPRequestHandler de la petición (escape hatch; casi nunca necesario)
    user: dict   # usuario autenticado (require() ya pasó): {"org_roles": {...}, ...}
    org: str     # organización activa ya resuelta y verificada como del usuario
    eng: Any     # Engine ligado al tenant (engine_for(org))
    qs: dict     # query string ya parseada (parse_qs): {clave: [valores]}

    @property
    def role(self) -> Optional[str]:
        return self.user["org_roles"].get(self.org)


# Un handler devuelve el payload JSON-serializable, o (payload, status).
HandlerFn = Callable[[Ctx], Any]


@dataclass(frozen=True)
class RouteSpec:
    method: str
    path: str
    cap: str
    handler: HandlerFn


class RouteRegistry:
    """Tabla (método, ruta exacta) -> RouteSpec. Sin patrones ni prefijos:
    las rutas con parámetros en el path siguen en la cadena legacy hasta que
    un incremento futuro las necesite aquí."""

    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], RouteSpec] = {}

    def route(self, method: str, path: str, *, cap: str) -> Callable[[HandlerFn], HandlerFn]:
        """Decorador de registro. `cap` es obligatoria y no vacía: el invariante
        de seguridad se aplica al registrar (arranque del proceso), nunca se
        descubre en producción."""
        if not isinstance(cap, str) or not cap.strip():
            raise ValueError(
                f"ruta {method} {path}: capability obligatoria y no vacía "
                f"(recibido {cap!r})"
            )
        key = (method.upper(), path)

        def _register(fn: HandlerFn) -> HandlerFn:
            if key in self._routes:
                raise ValueError(f"ruta duplicada en el registro: {method} {path}")
            self._routes[key] = RouteSpec(method.upper(), path, cap.strip(), fn)
            return fn

        return _register

    def specs(self) -> list[RouteSpec]:
        """Snapshot del registro (para tests e introspección)."""
        return list(self._routes.values())

    def dispatch(self, method: str, path: str, ctx: Ctx,
                 send: Callable[..., None]) -> bool:
        """Ejecuta el ritual completo para una ruta registrada.

        Devuelve True si la petición fue atendida (respuesta ya enviada por
        `send(payload, status)`), False si la ruta no está registrada y debe
        caer a la cadena legacy. `send` se inyecta (no se crea aquí) para que
        producción use `_send_json` y los tests capturen la respuesta.
        """
        spec = self._routes.get((method.upper(), path))
        if spec is None:
            return False
        if not AuthStore.can(ctx.role, spec.cap):
            send(dict(DENIED), 403)
            return True
        result = spec.handler(ctx)
        if isinstance(result, tuple):
            payload, status = result
        else:
            payload, status = result, 200
        send(payload, status)
        return True
