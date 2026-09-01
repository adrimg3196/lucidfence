#!/usr/bin/env python3
"""
Agent-Issue-Triage: lee issues abiertos, clasifica por prioridad,
asigna ownership y prepara acciones.
Ejecución autónoma — no requiere aprobación.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WHICH = Path(__file__).name
REPO = Path("/Users/adri/lucidfence").resolve()
CD = f"cd {REPO} &&"


def gh(*args: str) -> str:
    cmd = CD + " " + subprocess.list2cmdline(["gh"] + list(args))
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print(f"  [gh error] {' '.join(args)}: {r.stderr.strip()[:120]}", file=sys.stderr)
        return ""
    return r.stdout.strip()


def classify_issue(number: int, title: str, labels: list[str],
                   body: str = "", creator: str = "") -> dict:
    """Clasifica un issue por prioridad información disponible."""

    label_names = [l.lower() for l in labels]
    has_p1 = any("p1" in l for l in label_names)
    has_p2 = any("p2" in l for l in label_names)
    has_bug = any("bug" in l for l in label_names)
    has_docs = any("docs" in l or "documentation" in l for l in label_names)
    has_seo = any("seo" in l for l in label_names)
    has_security = any("security" in l or "crypto" in l or "webhooks" in l for l in label_names)
    has_feature = any("feature" in l or "nova" in l or "opportunity" in l for l in label_names)
    has_meta = any("meta" in l or "triage" in l or "chore" in l for l in label_names)

    # Prioridad por defecto — si no hay label P1/P2 ni docs, queda backlog
    priority = "P4 — backlog"

    # Prioridad calculada — primero por label, después por contenido del título

    if has_p1:
        if has_bug:
            priority = "P1 — bug crítico"
        elif has_security:
            priority = "P1 — seguridad"
        elif has_docs:
            priority = "P1 — docs"
        else:
            priority = "P1 — alta prioridad"
    elif has_p2:
        if has_bug:
            priority = "P2 — bug"
        elif has_feature:
            priority = "P2 — feature"
        else:
            priority = "P2 — mejora"
    elif has_docs or has_seo:
        priority = "P3 — documentación"
    elif has_meta:
        priority = "P3 — organización"

    # Si no hay label P1/P2 pero el título lo indica, re-elevar
    if priority.startswith("P3") or priority.startswith("P4"):
        title_lower = title.lower()
        if "p1" in title_lower or "[p1]" in title_lower or "prioridad #1" in title_lower:
            priority = "P1 — alta prioridad"
        elif "p2" in title_lower or "[p2]" in title_lower or "prioridad #2" in title_lower:
            priority = "P2 — mejora"

    # Categoría
    if has_security:
        category = "Security"
    elif has_docs or has_seo:
        category = "Docs/SEO"
    elif has_bug:
        category = "Bug"
    elif has_feature or "nova" in title.lower():
        category = "Feature/Nova"
    elif "webhooks" in title.lower() or "ocsf" in title.lower() or "caep" in title.lower():
        category = "Interoperability"
    elif "privacy" in title.lower() or "datos" in title.lower() or "geofencing" in title.lower():
        category = "Privacy/Geo"
    elif "crypto" in title.lower() or "cve" in title.lower():
        category = "Crypto/Vuln"
    elif "ai" in title.lower() or "governance" in title.lower():
        category = "AI Governance"
    elif "lifecycle" in title.lower() or "soporte" in title.lower() or "os" in title.lower():
        category = "Lifecycle"
    elif "byod" in title.lower() or "dex" in title.lower():
        category = "BYOD/DEX"
    elif "roadmap" in title.lower() or "vision" in title.lower():
        category = "Roadmap"
    else:
        category = "General"

    # Acción recomendada
    if has_bug and ("test" in body.lower() or "repro" in body.lower()):
        action = "Reproducir + fix + test"
    elif has_bug:
        action = "Investigar root cause + fix"
    elif has_docs or has_seo:
        action = "Redactar + publicar"
    elif has_feature or "nova" in title.lower():
        action = "Scope + implementar + PR"
    elif "karpathy" in title.lower():
        action = "Verificar hallazgos + documentar"
    elif "roadmap" in title.lower() or "vision" in title.lower():
        action = "Validar con CTO + integrar"
    else:
        action = "Evaluar + priorizar"

    return {
        "number": number,
        "title": title,
        "priority": priority,
        "category": category,
        "action": action,
        "labels": labels,
        "creator": creator,
    }


def triage_issue(number: int, classification: dict) -> None:
    """Deja un comentario de triaje en el issue."""

    body = (
        f"## Triaje automático ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')})\n\n"
        f"- **Prioridad:** {classification['priority']}\n"
        f"- **Categoría:** {classification['category']}\n"
        f"- **Acción recomendada:** {classification['action']}\n"
        f"- **Etiquetas actuales:** {', '.join(classification['labels']) or 'ninguna'}\n\n"
        f"Este triaje fue generado automáticamente. Si la clasificación no es correcta, "
        f"reejir las etiquetas y comentar."
    )
    r = gh("issue", "comment", str(number), "--body", body)
    if r:
        print(f"  ✓ Issue #{number}: triaje añadido")
    else:
        print(f"  ✗ Issue #{number}: fallo al comentar")


def main() -> None:
    print(f"[{WHICH}] Escaneando issues abiertos...")
    out = gh("issue", "list", "--state", "open", "--limit", "25",
             "--json", "number,title,labels,state,createdAt",
             "--jq", '.[] | "\(.number)|\(.title)|\(.labels | map(.name) | join(\",\"))|\(.state)"')
    if not out:
        print("  No hay issues abiertos.")
        return

    results = []
    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 4:
            continue
        number = int(parts[0])
        title = parts[1]
        labels_str = parts[2]
        state = parts[3]

        labels = [l.strip() for l in labels_str.split(",") if l.strip()] if labels_str else []

        classification = classify_issue(number, title, labels)
        results.append(classification)

        print(f"  #{number} [{classification['priority']}] [{classification['category']}] {title[:50]}...")

    # Resumen
    print(f"\n[{WHICH}] Resumen de triaje:")
    print(f"  Total issues: {len(results)}")

    by_priority = {}
    by_category = {}
    for r in results:
        by_priority.setdefault(r["priority"], []).append(r["number"])
        by_category.setdefault(r["category"], []).append(r["number"])

    print("\n  Por prioridad:")
    for p in ["P1 — bug crítico", "P1 — seguridad", "P1 — docs", "P1 — alta prioridad",
              "P2 — bug", "P2 — feature", "P2 — mejora", "P3 — documentación",
              "P3 — organización", "P4 — backlog"]:
        if p in by_priority:
            print(f"    {p}: #{', #'.join(str(n) for n in by_priority[p])}")

    print("\n  Por categoría:")
    for c in ["Security", "Docs/SEO", "Bug", "Feature/Nova", "Interoperability",
              "Privacy/Geo", "Crypto/Vuln", "AI Governance", "Lifecycle",
              "BYOD/DEX", "Roadmap", "General"]:
        if c in by_category:
            print(f"    {c}: #{', #'.join(str(n) for n in by_category[c])}")

    # Dejar triaje en issues seleccionados (P1 y P2)
    print(f"\n[{WHICH}] Aplicando triaje a issues P1/P2...")
    for r in results:
        if "P1" in r["priority"] or "P2" in r["priority"]:
            triage_issue(r["number"], r)

    # Guardar registro
    log_path = REPO / "docs" / "internal" / "issue_triage_log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(f"\n## Triaje {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n")
        for r in sorted(results, key=lambda x: (x["priority"], x["number"])):
            f.write(f"- `#{r['number']}` [{r['priority']}] [{r['category']}] {r['title']}\n")
        f.write("\n")

    print(f"[{WHICH}] Registro guardado en {log_path.relative_to(REPO)}")
    print(f"[{WHICH}] Completado: {len(results)} issues triados.")


if __name__ == "__main__":
    main()
