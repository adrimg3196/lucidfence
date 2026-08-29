#!/usr/bin/env python3.11
"""
gtm_claim_linter.py — Gate de messaging para LucidFence (canal CTO).

Escanea borradores de copy de marketing/GTM y flagga dos clases de riesgo de
integridad pública (riesgo #110):

  [POSITIONING] Re-introducción de posicionamiento de MODELO DE NEGOCIO descartado.
      Prohibido en CUALQUIER superficie pública (fuente de verdad:
      docs/gtm/revenue-model.md 2026-07-27 + docs/internal/STATE.md override
      2026-08-16). El producto es 100% free OSS (Apache-2.0): core + SOAR
      (core/soar.py) + SSO OIDC (saas/oidc.py) ya son libres en main.
      Frases prohibidas (ver t_0a1ba0d1 / COORD_TASK_launchcopy-enterprise.md):
        - tier/edición "Enterprise" pagada, open-core, "capa cerrada".
        - "on-prem cerrada", "SOAR/SSO/escala solo enterprise",
          "acceso anticipado a capas on-prem".
        - pricing, planes de pago, "managed/servicio gestionado como captura",
          "nos compra un UEM".
        - framing "Free / Pro / Enterprise".

  [TECHNICAL]  Matiz técnico de #188 no anclado a evidencia de runtime
      (flag opcional --technical; ya cubierto por RED LINE en outbox/README.md):
        - "Intune/Jamf live" incondicional (requiere token del cliente).
        - "webhook SOAR SSRF-hardened / egress RFC1918" (el hardening real es
          HMAC-SHA256 por tenant; RFC1918 vive solo en oidc.py).

Diseño anti-false-positive:
  - Las frases que aparecen DENTRO de contexto de negación/reconciliación
    ("eliminado", "fue", "reconciliado", "superseded", "descartado", "no ",
    "sin ", "removed", "was ") se downgradean a INFO (nota de reconciliación),
    no a BLOCK. Así los banners RECONCILIADO / SUPERSEDED no bloquean.
  - Se puede omitir patrones con --skip (glob) y forzar scope con --scope.

Archivos canónicos de co-firma (gap t_565b1493):
  Los archivos docs/gtm/CTO_CHANNEL.md y .cto_input_188.md viven FUERA de
  outbox/ pero son la fuente de verdad de la co-firma CTO↔Marketing. Para que
  las co-firmas técnicas sobre ellos NO escapen al lint, --scope outbox los
  INCLUYE por defecto (se pueden desactivar con --no-canonical). También se
  pueden pasar sus rutas explícitas como argumentos.

Exit code: 0 si no hay BLOCK; 1 si hay al menos un BLOCK de POSITIONING.
Uso típico (CTO/CEO en el gate de outreach):
  python3.11 scripts/gtm_claim_linter.py docs/gtm/outbox/2026-08-20-x-thread.md
  python3.11 scripts/gtm_claim_linter.py docs/gtm/outbox/ --scope outbox
  python3.11 scripts/gtm_claim_linter.py docs/gtm/outbox/ --scope outbox --technical
  # --scope outbox YA escanea los archivos canónicos (CTO_CHANNEL.md,
  # .cto_input_188.md). Para omitirlos: --no-canonical.
  python3.11 scripts/gtm_claim_linter.py --technical \\
      docs/gtm/CTO_CHANNEL.md .cto_input_188.md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Reglas de POSITIONING (modelo de negocio descartado). severity por defecto BLOCK.
# Cada regla: (id, descripción, regex, negation_exempt). IGNORECASE siempre.
#   negation_exempt=True -> la regla se downgradea a INFO cuando la frase aparece
#     dentro de contexto de negación/reconciliación (ver NEGATION_TOKENS), de modo
#     que un SOP de gobernanza que *enumera* frases prohibidas no bloquea su propio
#     gate. TODAS las reglas de posicionamiento comparten esta exención de forma
#     explícita y auditable (cierra la asimetría histórica POS-LAYER-CLOSED /
#     POS-BUYS-UEM, tarea t_bdc60b29). Poner False solo si una regla debe bloquear
#     SIEMPRE, pase lo que pase en la oración.
POSITIONING_RULES: list[tuple[str, str, str, bool]] = [
    ("POS-OPENCORE", "modelo open-core descartado", r"open[- ]?core", True),
    ("POS-ONPREM-CLOSED", "on-prem cerrada", r"on[- ]?prem\s+cerrad", True),
    ("POS-LAYER-CLOSED", "capa cerrada / capa Enterprise", r"capa\s+(enterprise|cerrada)", True),
    ("POS-MODULE-ENT", "módulo Enterprise", r"m[óo]dulo\s+enterprise", True),
    ("POS-ENT-ONPREM", "Enterprise on-prem", r"enterprise\s+on[- ]?prem", True),
    ("POS-ENT-PAID", "edición/tier Enterprise pagada",
     r"(edici[óo]n|tier)\s+(enterprise|pag)", True),
    ("POS-ENT-WORDS", "Enterprise con cerrado/pagado/on-prem",
     r"enterprise\s+(cerrad|pag|tier|edici|on[- ]?prem)", True),
    ("POS-PLANS-PAID", "planes de pago / pricing", r"(planes?\s+de\s+pago|pricing)", True),
    ("POS-MANAGED-CAPTURE", "servicio gestionado como captura",
     r"(servicio\s+gestionado\s+como\s+captura|managed.*captura)", True),
    ("POS-BUYS-UEM", "nos compra un UEM", r"nos\s+compra\s+un\s+uem", True),
    ("POS-SOLO-ENT", "SOAR/SSO/escala solo enterprise",
     r"(soar|sso|escala).{0,20}solo\s+enterprise", True),
    ("POS-EARLY-ONPREM", "acceso anticipado a capas on-prem",
     r"acceso\s+anticipado\s+a\s+(las\s+)?capas?\s+on[- ]?prem", True),
    ("POS-FREEPROENT", "framing Free / Pro / Enterprise",
     r"free\s*/\s*pro(?:\s*/\s*enterprise)?", True),
]

# ---------------------------------------------------------------------------
# Reglas de TECHNICAL (#188 matiz). severity por defecto BLOCK, pero solo se
# activan con --technical.
# ---------------------------------------------------------------------------
TECHNICAL_RULES: list[tuple[str, str, str, bool]] = [
    ("TEC-INTUNE-LIVE", "Intune/Jamf 'live' incondicional (requiere token)",
     r"(intune|jamf)\s+(live|en\s+vivo)", True),
    ("TEC-WEBHOOK-SSRF", "webhook SOAR 'SSRF-hardened/egress RFC1918' (real: HMAC por tenant)",
     r"webhook.{0,30}(ssrf|rfc\s?1918|egress)", True),
]

# Tokens que indican contexto de reconciliación/negación -> downgrade a INFO.
NEGATION_TOKENS = [
    "eliminado", "fue", "reconciliado", "reconcil", "superseded", "supersede",
    "descartado", "remov", "removed", "was ", "ya no", "no ", "sin ", "nunca",
    "prohibido", "banner", "corregido",
]

DEFAULT_SKIP_GLOBS = ["*README.md", "**/SUPERSEDED*", "**/*SUPERSEDED*"]

# Archivos canónicos de co-firma CTO↔Marketing. Viven FUERA de outbox/ pero son
# la fuente de verdad de las co-firmas técnicas. Sin incluirllos, las co-firmas
# sobre CTO_CHANNEL.md / .cto_input_188.md escapaban al lint cuando se usaba solo
# --scope outbox (gap documentado en t_565b1493).
CANONICAL_COSIGN_FILES: list[Path] = [
    Path("docs/gtm/CTO_CHANNEL.md"),
    Path(".cto_input_188.md"),
]


def compile_rules(rules: list[tuple[str, str, str, bool]]
                  ) -> list[tuple[str, str, re.Pattern, bool]]:
    compiled = []
    for rid, desc, pat, exempt in rules:
        compiled.append((rid, desc, re.compile(pat, re.IGNORECASE), bool(exempt)))
    return compiled


def iter_target_files(paths: list[str], skip_globs: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        pp = Path(p)
        if pp.is_file():
            files.append(pp)
        elif pp.is_dir():
            files.extend(sorted(pp.rglob("*.md")))
    # aplicar skip globs
    kept: list[Path] = []
    for f in files:
        rel = str(f)
        if any(f.match(g) or f.name.lower().endswith(g.lstrip("*").lower())
               or g.replace("**/", "").replace("*", "") in rel for g in skip_globs):
            continue
        kept.append(f)
    # dedupe
    return sorted(set(kept))


def scan_file(path: Path, rules: list[tuple[str, str, re.Pattern, bool]], category: str
              ) -> list[dict]:
    findings: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] no se pudo leer {path}: {exc}", file=sys.stderr)
        return findings
    for i, line in enumerate(text.splitlines(), start=1):
        for rid, desc, rx, negation_exempt in rules:
            m = rx.search(line)
            if not m:
                continue
            matched = m.group(0)
            lowered = line.lower()
            # Downgrade a INFO cuando la regla es negation_exempt Y la frase
            # aparece en contexto de negación/reconciliación. Así un SOP que
            # *enumera* frases prohibidas (p.ej. "NUNCA 'capa cerrada'") no
            # bloquea su propio gate. (t_bdc60b29: todas las reglas POS lo son.)
            negated = negation_exempt and any(tok in lowered for tok in NEGATION_TOKENS)
            severity = "INFO" if negated else "BLOCK"
            findings.append({
                "file": str(path), "line": i, "rule": rid, "category": category,
                "desc": desc, "match": matched, "severity": severity,
                "text": line.strip(),
            })
    return findings


def resolve_targets(paths: list[str], skip_globs: list[str],
                    include_canonical: bool) -> list[Path]:
    """Resuelve la lista final de archivos a escanear.

    Cuando include_canonical=True, los archivos canónicos de co-firma se
    INCLUYEN SIEMPRE (se saltan los skip_globs a propósito: son la fuente de
    verdad del canal CTO y no deben poder eludir el gate por un glob).
    """
    targets = iter_target_files(paths, skip_globs)
    if include_canonical:
        for cf in CANONICAL_COSIGN_FILES:
            if cf.exists() and cf.is_file() and cf not in targets:
                targets.append(cf)
    return sorted(set(targets))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="GTM claim linter (POSITIONING + TECHNICAL gate)")
    ap.add_argument("paths", nargs="*", help="archivos o directorios .md a escanear "
                    "(opcional si se usa --scope)")
    ap.add_argument("--technical", action="store_true",
                    help="también aplica reglas de matiz técnico #188")
    ap.add_argument("--scope", default=None,
                    help="atajo: 'outbox' -> escanea docs/gtm/outbox sin README.md")
    ap.add_argument("--canonical", dest="canonical", action="store_true", default=None,
                    help="(implícito con --scope outbox) también escanea los archivos "
                         "canónicos de co-firma CTO_CHANNEL.md y .cto_input_188.md")
    ap.add_argument("--no-canonical", dest="canonical", action="store_false",
                    help="no incluir los archivos canónicos de co-firma")
    ap.add_argument("--skip", action="append", default=None,
                    help="glob a omitir (acumulable)")
    ap.add_argument("--quiet", action="store_true", help="solo BLOCK")
    args = ap.parse_args(argv)

    skip_globs = list(DEFAULT_SKIP_GLOBS)
    if args.skip:
        skip_globs.extend(args.skip)

    paths = list(args.paths)
    if args.scope == "outbox":
        # relativo al repo (donde se invoca)
        outbox = Path("docs/gtm/outbox")
        if outbox.exists():
            paths = [str(outbox)]
        skip_globs = list(DEFAULT_SKIP_GLOBS)  # ya excluye README.md

    # --scope outbox IMPLICA --canonical (t_565b1493: cierra el punto ciego de
    # co-firma sobre CTO_CHANNEL.md / .cto_input_188.md). Se puede desactivar
    # explícitamente con --no-canonical.
    include_canonical = args.canonical if args.canonical is not None else (args.scope == "outbox")

    if not paths and not include_canonical:
        ap.error("debe indicar al menos un path o usar --scope outbox")

    pos_rules = compile_rules(POSITIONING_RULES)
    tech_rules = compile_rules(TECHNICAL_RULES) if args.technical else []

    targets = resolve_targets(paths, skip_globs, include_canonical)
    if not targets:
        print("[WARN] ningún archivo .md coincidente tras skip.", file=sys.stderr)

    all_findings: list[dict] = []
    for f in targets:
        all_findings.extend(scan_file(f, pos_rules, "POSITIONING"))
        if tech_rules:
            all_findings.extend(scan_file(f, tech_rules, "TECHNICAL"))

    blocks = [x for x in all_findings if x["severity"] == "BLOCK"]
    infos = [x for x in all_findings if x["severity"] == "INFO"]

    print(f"== gtm_claim_linter :: {len(targets)} archivo(s) escaneado(s) "
          f"(canónicos={'sí' if include_canonical else 'no'}) ==")
    if blocks:
        print(f"\n[BLOCK] {len(blocks)} hallazgo(s) de POSICIONAMIENTO DESCARTADO "
              f"(debe corregirse antes de publicar):")
        for x in blocks:
            print(f"  - {x['file']}:{x['line']} [{x['rule']}] {x['desc']}")
            print(f"      > {x['text']}")
    if infos and not args.quiet:
        print(f"\n[INFO] {len(infos)} referencia(s) en contexto de reconciliación "
              f"(no bloquea, revisar que no sea copy vivo):")
        for x in infos:
            print(f"  - {x['file']}:{x['line']} [{x['rule']}] {x['desc']}")
            print(f"      > {x['text']}")
    if not all_findings:
        print("\n[OK] sin frases prohibidas de posicionamiento ni matiz técnico.")

    print(f"\nResumen: {len(blocks)} BLOCK, {len(infos)} INFO.")
    return 1 if blocks else 0


if __name__ == "__main__":
    raise SystemExit(main())
