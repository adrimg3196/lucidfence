#!/usr/bin/env python3
"""Parsea el body de un issue de signup de LucidFence y crea el tenant.

El formulario de la landing/vitrina genera un issue con un bloque delimitado:

    <!-- lucidfence-signup -->
    tenant_id: empresa-xyz
    fleet: [{"id":"d1","name":"Camion 1","platform":"android","lat":40.42,"lng":-3.70,"compliant":true,"department":"Reparto"}]
    fences: [{"id":"hq","name":"HQ","kind":"circle","center":{"lat":40.42,"lng":-3.70},"radius_m":500}]
    <!-- /lucidfence-signup -->

Este script extrae el bloque, valida el tenant_id y llama a saas_api_op.create_tenant.
No expone tokens: corre en Actions con GITHUB_TOKEN (permisos mínimos del repo).
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(ROOT))

START = "<!-- lucidfence-signup -->"
END = "<!-- /lucidfence-signup -->"


def parse_block(body: str):
    s = body.find(START)
    e = body.find(END)
    if s < 0 or e < 0 or e <= s:
        raise ValueError("bloque lucidfence-signup no encontrado en el issue")
    block = body[s + len(START):e].strip()
    data = {"tenant_id": None, "fleet": [], "fences": []}
    # tenant_id en su propia línea
    m = re.search(r"^tenant_id:\s*(.+)$", block, re.MULTILINE)
    if m:
        data["tenant_id"] = m.group(1).strip()
    # fleet / fences como JSON en su propia línea (array en una sola línea)
    for key in ("fleet", "fences"):
        mj = re.search(rf"^{key}:\s*(\[.*\])\s*$", block, re.MULTILINE)
        if mj:
            try:
                data[key] = json.loads(mj.group(1))
            except Exception as ex:
                raise ValueError(f"{key} no es JSON válido: {ex}")
    if not data["tenant_id"]:
        raise ValueError("tenant_id vacío")
    return data


def main():
    body = os.environ.get("ISSUE_BODY", "")
    # GitHub Actions puede entregar ISSUE_BODY vacío cuando el cuerpo del issue
    # es multilínea/comillas (escapado roto en `env:`). En ese caso, leemos el
    # body fresco desde la API del repo (sin tokens del usuario).
    if not body and os.environ.get("ISSUE_NUMBER"):
        import subprocess
        try:
            out = subprocess.run(
                ["gh", "issue", "view", os.environ["ISSUE_NUMBER"], "--json", "body",
                 "--jq", ".body"],
                capture_output=True, text=True, check=True,
            )
            body = out.stdout
        except Exception as ex:
            print(f"No se pudo leer el body del issue vía gh: {ex}")
    if not body:
        print("ISSUE_BODY vacío")
        sys.exit(1)
    try:
        data = parse_block(body)
    except ValueError as e:
        print(f"ERROR parseando signup: {e}")
        sys.exit(1)

    from scripts.saas_api_op import create_tenant, _tenant_dir  # importa módulo
    # validar tenant_id (alfanumérico, -, _)
    try:
        _tenant_dir(data["tenant_id"])
    except ValueError as e:
        print(f"tenant_id inválido: {e}")
        sys.exit(1)

    if not data["fleet"]:
        # flota mínima de ejemplo si el prospecto no especificó devices
        data["fleet"] = [{"id": "d1", "name": "Dispositivo demo", "platform": "android",
                           "lat": 40.4210, "lng": -3.7080, "compliant": True,
                           "department": "General"}]
    if not data["fences"]:
        data["fences"] = [{"id": "hq", "name": "Sede", "kind": "circle",
                            "center": {"lat": 40.4210, "lng": -3.7080}, "radius_m": 500}]

    create_tenant(data["tenant_id"], {"fleet": data["fleet"], "fences": data["fences"]})
    print(f"Tenant '{data['tenant_id']}' creado desde issue #{os.environ.get('ISSUE_NUMBER','?')}")


if __name__ == "__main__":
    main()
