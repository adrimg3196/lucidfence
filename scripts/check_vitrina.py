#!/usr/bin/env python3
"""check_vitrina — EL verificador único de la vitrina pública.

Una sola fuente de verdad para (a) la URL canónica del snapshot publicado y
(b) su esquema, importado del propio publisher (PUBLISHED_REQUIRED_KEYS).
Todos los workflows (nightly-health-check, monitor-hourly) llaman a este
script en vez de llevar copias inline de curl+python: así la URL y el
esquema no pueden derivar entre superficies — la familia de fallos de
2026-08-20 (checker con esquema viejo, monitor con URL vieja) queda
estructuralmente cerrada.

Uso:
    python3 scripts/check_vitrina.py            # reachability + esquema
    python3 scripts/check_vitrina.py --url-only # imprime la URL canónica

Exit 0 = vitrina viva y esquema válido. Stdlib only.
"""
from __future__ import annotations

import json
import sys
import urllib.request

sys.path.insert(0, __file__.rsplit("/", 2)[0])
# El contrato del snapshot se importa del modulo HOJA published_schema, NO de
# cloud_publisher: ese arrastra engine -> actions -> adapters -> applivery ->
# `import requests`, y nightly-health-check.yml corre este script sin pip
# install. Ese acoplamiento dejo la alarma nocturna en rojo 10 dias seguidos
# (2026-08-13..08-22, ModuleNotFoundError: requests) con la vitrina viva.
# published_schema no importa nada: este script sigue siendo stdlib puro y la
# fuente del esquema sigue siendo una sola (cloud_publisher la reexporta).
from lucidfence.core.published_schema import PUBLISHED_REQUIRED_KEYS  # noqa: E402

# La URL canónica del snapshot vivo. data/cloud_state.json vive en la rama de
# datos cloud-state (nunca en main — ver docs/adr/ADR-0011). La vitrina
# (static/cloud.html) y el test de self-service DEBEN usar esta misma URL;
# tests/test_single_source_cloud_state.py lo hace cumplir.
CANONICAL_URL = ("https://raw.githubusercontent.com/adrimg3196/lucidfence/"
                 "cloud-state/data/cloud_state.json")

TIMEOUT_S = 30


def main() -> int:
    if "--url-only" in sys.argv:
        print(CANONICAL_URL)
        return 0
    try:
        with urllib.request.urlopen(CANONICAL_URL, timeout=TIMEOUT_S) as r:
            raw = r.read()
    except Exception as exc:
        print(f"::error::Vitrina NO alcanzable: {CANONICAL_URL} ({type(exc).__name__}: {exc})")
        return 1
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"::error::La vitrina responde pero no es JSON válido: {exc}")
        return 1
    missing = [k for k in PUBLISHED_REQUIRED_KEYS if k not in data]
    if missing:
        print(f"::error::Esquema de vitrina incompleto — faltan claves: {missing}")
        return 1
    if not isinstance(data.get("devices"), list) or not isinstance(data.get("fences"), list):
        print("::error::devices/fences deben ser listas")
        return 1
    if data.get("totals", {}).get("devices") != len(data["devices"]):
        print("::error::totals.devices no cuadra con len(devices)")
        return 1
    print(f"OK: vitrina viva y esquema válido ({len(data['devices'])} devices, "
          f"{len(data['fences'])} fences)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
