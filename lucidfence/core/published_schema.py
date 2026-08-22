"""Contrato publico del snapshot de la vitrina — modulo HOJA, stdlib puro.

Por que existe este fichero y no vive dentro de cloud_publisher.py:

`scripts/check_vitrina.py` es EL verificador de la vitrina y su docstring
promete "stdlib only", porque `nightly-health-check.yml` lo ejecuta SIN
instalar dependencias. Cuando importaba el contrato desde
`lucidfence.core.cloud_publisher`, arrastraba la cadena
cloud_publisher -> core.engine -> core.actions -> core.adapters -> applivery,
y applivery hace `import requests` a nivel de modulo. Resultado real: el
health-check nocturno fallo 10 dias seguidos (2026-08-13 .. 2026-08-22) con
`ModuleNotFoundError: No module named 'requests'` — una alarma en rojo
permanente no puede alertar de nada, y la vitrina estaba perfectamente viva
todo ese tiempo.

Este modulo no importa NADA. Es la unica fuente del contrato:
`cloud_publisher` lo reexporta (misma tupla, identidad preservada) y
`check_vitrina` lo importa directo, asi que el esquema sigue siendo uno solo
y el verificador vuelve a ser ejecutable con Python desnudo.

Regla: si el publisher cambia el esquema del snapshot, se cambia AQUI.
"""
from __future__ import annotations

# Las claves que TODO consumidor del snapshot (vitrina, health-checks,
# monitor) puede exigir.
PUBLISHED_REQUIRED_KEYS = ("service", "generated_at", "mode", "totals",
                          "tenants", "devices", "fences")

__all__ = ["PUBLISHED_REQUIRED_KEYS"]
