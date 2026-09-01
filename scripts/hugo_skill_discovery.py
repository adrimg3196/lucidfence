#!/usr/bin/env python3
"""
Script para Hugo (v0.15+): buscar skills/plugins nuevos en GitHub
relevantes para los agentes de LucidFence, extraerlos desde @HermesWatcher,
y registrarlos en loop-run-log.md.

Uso: hugo skill-discovery
       hugo skill-discovery --perfiles="empresa-cto,empresa-test-qa"
       hugo skill-discovery --feed-only

Dependencias: Python 3.11+ (stdlib-only: urllib, gzip, re, html)
El script descarga y parsea el feed de @HermesWatcher para detectar
menciones de skills/plugins nuevos, luego los instala en los perfiles
especificados (o en todos los perfiles de LucidFence si no se especifican).
"""

import os
import sys
import re
import html
import gzip
import io
import shutil
import argparse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from datetime import datetime

# --- Configuración ---
HERMES_WATCHER_URL = "https://x.com/HermesWatcher?s=11"
PROFILES_DIR = Path("/Users/adri/.hermes/profiles")
HERMES_SKILLS_DIR = Path("/Users/adri/.hermes")
LUCIDFENCE_DIR = Path("/Users/adri/lucidfence")
LOG_FILE = LUCIDFENCE_DIR / "docs/internal/loop-run-log.md"
TIMESTAMP = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

# Perfiles por defecto donde instalar skills relevantes
DEFAULT_PROFILES = [
    "empresa-test-qa",
    "empresa-cto",
    "empresa-devops-release",
    "empresa-product",
    "empresa-seo-docs",
    "empresa-security-soc",
    "empresa-marketing",
    "empresa-finance",
    "empresa-kit-bot",
    "empresa-selfimprove",
]

# Categorías de skills que buscamos en ~/.hermes
SKILL_CATEGORIES = [
    "software-development",
    "devops",
    "research",
    "autonomous-ai-agents",
    "productivity",
    "web-development",
    "creative",
    "social-media",
    "email",
    "cloud-state-impact-check",
    "lucidfence-contrib",
]


def fetch_feed(url: str) -> str | None:
    """Descargar el feed de @HermesWatcher y extraer el texto limpio.

    Retorna el texto plano de la página o None si falla.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://x.com/",
    }

    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read()

            if resp.headers.get("Content-Encoding") == "gzip":
                with gzip.GzipFile(fileobj=io.BytesIO(raw)) as f:
                    raw = f.read()

            text = raw.decode("utf-8", errors="replace")

            # Limpiar HTML para obtener texto plano
            text = re.sub(
                r'<script[^>]*>.*?</script>',
                '',
                text,
                flags=re.DOTALL | re.IGNORECASE,
            )
            text = re.sub(
                r'<style[^>]*>.*?</style>',
                '',
                text,
                flags=re.DOTALL | re.IGNORECASE,
            )
            text = re.sub(r'<[^>]+>', ' ', text)
            text = html.unescape(text)
            text = re.sub(r'\s+', ' ', text).strip()

            return text

    except HTTPError as e:
        print(f"Error HTTP al descargar feed: {e.code} {e.reason}", file=sys.stderr)
        return None
    except URLError as e:
        print(f"Error de red al descargar feed: {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error inesperado al descargar feed: {e}", file=sys.stderr)
        return None


def extract_posts(feed_text: str) -> list[dict]:
    """Extraer los posts más recientes del feed de HermesWatcher.

    Retorna lista de diccionarios con 'text' (fragmento del post).
    """
    posts = []

    # Buscar fragmentos que parezcan posts individuales
    # El feed tiene texto mezclado: header del perfil + posts + UI
    # Los posts suelen aparecer después de '@HermesWatcher' o como
    # textos que empiezan con tiempo relativo (4h, 7h, 16 ago, etc.)

    # Patrón 1: texto después de @HermesWatcher
    sections = text.split("@HermesWatcher")
    for section in sections[1:]:
        # Quitar el header del perfil que aparece al principio
        section = re.sub(
            r'^[^\n]*Iniciar sesión[^\n]*\n',
            '',
            section,
            flags=re.IGNORECASE,
        )
        section = re.sub(
            r'^[^\n]*Regístrate[^\n]*\n',
            '',
            section,
            flags=re.IGNORECASE,
        )
        section = section.strip()
        if len(section) > 20:
            posts.append({"text": section[:500]})

    # Patrón 2: buscar tiempo relativo como marcador de posts
    time_pattern = re.compile(
        r'(\d+[hjd]+\s+(?:hace|ago|fontal|antes|Después de))',
        re.IGNORECASE,
    )
    for match in time_pattern.finditer(text):
        start = match.start()
        end = min(len(text), start + 400)
        fragment = text[start:end].strip()
        if fragment and fragment not in [p["text"] for p in posts]:
            posts.append({"text": fragment})

    # Deduplicar por primeras 80 chars
    seen = set()
    unique_posts = []
    for post in posts:
        key = post["text"][:80]
        if key not in seen:
            seen.add(key)
            unique_posts.append(post)

    return unique_posts[:10]


def detect_skills_from_posts(posts: list[dict]) -> list[dict]:
    """De una lista de posts, detectar menciones de skills/plugins/capacidades.

    Retorna lista de dicts con 'name' (nombre de skill/capacidad) y
    'source' (fuente del descubrimiento).
    """
    detected = []

    for post in posts:
        text = post.get("text", "")

        # Detectar menciones de "skill" o "skill" como palabra clave
        if re.search(r'\bskill[s]?\b', text, re.IGNORECASE):
            # Buscar qué skill específico se menciona
            skill_refs = re.findall(
                r'skill[s]?\s+(?:de|para|is|are|can|can be|adds?)\s+([a-zA-Z][a-zA-Z0-9_-]{2,40})',
                text,
                re.IGNORECASE,
            )
            for ref in skill_refs:
                ref_lower = ref.lower().strip()
                if ref_lower not in [d["name"] for d in detected]:
                    detected.append({"name": ref_lower, "source": "HermesWatcher"})

        # Detectar menciones de "plugin"
        if re.search(r'\bplugin[s]?\b', text, re.IGNORECASE):
            plugin_refs = re.findall(
                r'plugin[s]?\s+(?:de|para|is|are|adds?|allows?)\s+([a-zA-Z][a-zA-Z0-9_-]{2,40})',
                text,
                re.IGNORECASE,
            )
            for ref in plugin_refs:
                ref_lower = ref.lower().strip()
                if ref_lower not in [d["name"] for d in detected]:
                    detected.append({"name": ref_lower, "source": "HermesWatcher"})

        # Detectar capacidades específicas mencionadas en el feed
        if re.search(r'\bbatch\s+processing\b', text, re.IGNORECASE):
            if "batch_processing" not in [d["name"] for d in detected]:
                detected.append({
                    "name": "batch_processing",
                    "source": "HermesWatcher",
                    "description": "Procesamiento por lotes de jobs",
                })

        if re.search(r'autonomous\s+delegation', text, re.IGNORECASE):
            if "autonomous_delegation" not in [d["name"] for d in detected]:
                detected.append({
                    "name": "autonomous_delegation",
                    "source": "HermesWatcher",
                    "description": "Delegación autónoma más confiable",
                })

        if re.search(r'\bsubagent[s]?\b', text, re.IGNORECASE):
            if "subagent" not in [d["name"] for d in detected]:
                detected.append({
                    "name": "subagent",
                    "source": "HermesWatcher",
                    "description": "Mejoras en manejo de subagents",
                })

        if re.search(r'\bkanban\b', text, re.IGNORECASE):
            if "kanban_plugin" not in [d["name"] for d in detected]:
                detected.append({
                    "name": "kanban_plugin",
                    "source": "HermesWatcher",
                    "description": "Plugin de kanban para Hermes Desktop",
                })

        if re.search(r'\bGPT-5\b|\bGTP-5\b|GPT5', text, re.IGNORECASE):
            if "gpt5_model" not in [d["name"] for d in detected]:
                detected.append({
                    "name": "gpt5_model",
                    "source": "HermesWatcher",
                    "description": "Nuevo modelo GPT-5 disponible",
                })

    return detected


def find_skill_path(skill_name: str) -> str | None:
    """Buscar un skill en ~/.hermes por nombre.

    Recorre todas las categorías y subcarpetas buscando un SKILL.md
    cuyo nombre de carpeta coincida con skill_name.

    Retorna la ruta relativa al skill o None si no se encuentra.
    """
    for category in SKILL_CATEGORIES:
        category_dir = HERMES_SKILLS_DIR / category
        if not category_dir.exists():
            continue

        for item in category_dir.iterdir():
            if item.is_dir():
                # Verificar si este directorio o sus subdirectorios
                # contienen el skill buscado
                if item.name == skill_name and (item / "SKILL.md").exists():
                    return f"{category}/{skill_name}"
                # Buscar en subdirectorios (ej: playwright-cli puede estar
                # en optional-skills/web-development/playwright-cli/)
                for subitem in item.rglob("SKILL.md"):
                    rel = subitem.relative_to(item)
                    if rel.parts and rel.parts[0] == skill_name:
                        return f"{category}/{rel}"

    # Búsqueda directa en cualquier lugar de ~/.hermes
    for skill_file in HERMES_SKILLS_DIR.rglob("SKILL.md"):
        rel = skill_file.relative_to(HERMES_SKILLS_DIR)
        parts = rel.parts
        if len(parts) >= 2:
            if parts[-1] == "SKILL.md" and parts[-2] == skill_name:
                return "/".join(parts[:-1])
        elif len(parts) == 1 and parts[0] == skill_name and skill_file.name == "SKILL.md":
            # Skill de una sola carpeta (raro pero posible)
            return skill_name

    return None


def install_skill_in_profile(skill_path: str, profile: str) -> bool:
    """Instalar un skill en un perfil específico.

    skill_path: ruta relativa dentro de ~/.hermes (ej: software-development/playwright-cli)
    profile: nombre del perfil (ej: empresa-cto)

    Retorna True si la instalación fue exitosa.
    """
    src_skill_dir = HERMES_SKILLS_DIR / skill_path
    src_skill_file = src_skill_dir / "SKILL.md"

    if not src_skill_file.exists():
        return False

    # Determinar destination
    if skill_path.startswith("hermes-agent/optional-skills/"):
        rel = skill_path.replace("hermes-agent/optional-skills/", "")
        parts = rel.split("/", 1)
        if len(parts) > 1:
            dst_dir = (
                PROFILES_DIR
                / profile
                / "skills"
                / parts[0]
                / parts[1]
            )
        else:
            dst_dir = PROFILES_DIR / profile / "skills" / rel
    else:
        parts = skill_path.split("/", 1)
        if len(parts) > 1:
            dst_dir = (
                PROFILES_DIR
                / profile
                / "skills"
                / parts[0]
                / parts[1]
            )
        else:
            dst_dir = PROFILES_DIR / profile / "skills" / skill_path

    dst_file = dst_dir / "SKILL.md"

    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_skill_file, dst_file)
        return True
    except Exception as e:
        print(f"Error instalando {skill_path} en {profile}: {e}", file=sys.stderr)
        return False


def get_installed_skills_in_profile(profile: str) -> set[str]:
    """Obtener conjunto de nombres de skills instalados en un perfil."""
    profile_dir = PROFILES_DIR / profile / "skills"
    if not profile_dir.exists():
        return set()

    installed = set()
    for skill_file in profile_dir.rglob("SKILL.md"):
        rel = skill_file.relative_to(profile_dir)
        parts = rel.parts
        if len(parts) >= 2:
            installed.add(f"{parts[0]}/{parts[1]}")
        else:
            installed.add(rel.stem)
    return installed


def find_relevant_skills_for_lucidfence(
    detected_skills: list[dict],
) -> list[dict]:
    """Filtrar las skills detectadas para encontrar las relevantes para LucidFence.

    LucidFence es un producto de geofencing/UEM multi-agente. Skills relevantes:
    - Testing/E2E (playwright, pruebas)
    - DevOps/Deploy (CI, release, version)
    - Security/Audit (scanning, review)
    - Code review / quality
    - Autonomous delegation (para los agentes del equipo)
    - Batch processing (para procesamiento masivo)
    - Research/analysis
    """
    relevant_keywords = [
        # Testing & QA
        "playwright", "testing", "test", "e2e", "quality",
        # DevOps & Release
        "deploy", "release", "version", "ci", "cd", "pipeline",
        # Security & Audit
        "security", "audit", "scan", "vulnerability", "review",
        # Code & Quality
        "code", "review", "linter", "refactor", "debug",
        # Agent capabilities
        "agent", "delegation", "subagent", "autonomous", "batch",
        # Research & Analysis
        "research", "analysis", "data", "metric",
        # Documentation
        "doc", "document", "readme", "wiki",
        # Web & UI
        "web", "browser", "page", "ui",
        # Git & Collaboration
        "git", "github", "pr", "merge",
    ]

    relevant = []
    for skill in detected_skills:
        name = skill["name"]
        # Verificar si el skill existe físicamente
        if find_skill_path(name):
            # Verificar relevancia por keyword
            for keyword in relevant_keywords:
                if keyword in name.lower():
                    relevant.append(skill)
                    break
            else:
                # Si no hay keyword match pero existe el skill,
                # asumimos que podría ser relevante (no descartamos)
                relevant.append(skill)
        else:
            # Skill mencionado pero no disponible localmente
            # Lo incluimos como "no disponible" para registro
            relevant.append(skill)

    return relevant


def register_in_loop_log(
    feed_text: str,
    posts: list[dict],
    detected_skills: list[dict],
    installed_skills: list[tuple[str, str]],
    new_capabilities: list[dict],
) -> None:
    """Registrar la ejecución del skill discovery en loop-run-log.md."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    skill_names = [s["name"] for s in detected_skills]
    installed_desc = ", ".join(
        f"{s}→{p}" for s, p in installed_skills
    ) if installed_skills else "ninguno"

    cap_names = [c["name"] for c in new_capabilities]

    entry = (
        f"- {TIMESTAMP} | L2 | Skill discovery (automejora) | "
        f"Feed @HermesWatcher consultado. "
        f"Posts relevantes: {len(posts)}. "
        f"Skills detectadas: {', '.join(skill_names) if skill_names else 'ninguna'}. "
        f"Skills instalados: {installed_desc}. "
        f"Capacidades nuevas detectadas: {', '.join(cap_names) if cap_names else 'ninguna'}. "
        f"Acción: instalar skills descubiertos en perfiles clave."
    )

    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")

    print(f"Registrado en {LOG_FILE}")


def main():
    parser = argparse.ArgumentParser(
        description="Buscar y instalar skills nuevos desde @HermesWatcher",
    )
    parser.add_argument(
        "--perfiles",
        type=str,
        default=None,
        help="Lista comma-separated de perfiles para instalar skills (default: todos los perfiles de LucidFence)",
    )
    parser.add_argument(
        "--feed-only",
        action="store_true",
        help="Solo extraer y mostrar el feed, sin instalar nada",
    )
    parser.add_argument(
        "--skills",
        type=str,
        default=None,
        help="Lista comma-separated de skills específicos a instalar",
    )

    args = parser.parse_args()

    # Determinar perfiles objetivo
    if args.perfiles:
        profiles = [p.strip() for p in args.perfiles.split(",")]
    else:
        profiles = DEFAULT_PROFILES

    # Determinar skills específicos si se solicitaron
    if args.skills:
        specific_skills = [s.strip() for s in args.skills.split(",")]
    else:
        specific_skills = None

    print("=" * 70)
    print("HUGO: Skill Discovery — Buscando skills nuevos en @HermesWatcher")
    print("=" * 70)

    # 1. Descargar feed
    print(f"\n[TIMESTAMP] {TIMESTAMP}")
    print("\n1. Descargando feed de @HermesWatcher ...")
    feed_text = fetch_feed(HERMES_WATCHER_URL)

    if feed_text is None:
        print("ERROR: No se pudo descargar el feed de HermesWatcher")
        print("El servicio está offline o está siendo bloqueado.")
        print("Saltando skill discovery hoy.")
        return 1

    if len(feed_text) < 100:
        print("ADVERTENCIA: Feed muy corto, posiblemente HTML de login")
        print("El contenido de X puede requerir autenticación.")

    print(f"   Feed descargado: {len(feed_text)} caracteres")

    # 2. Extraer posts
    print("\n2. Extrayendo posts recientes del feed ...")
    posts = extract_posts(feed_text)
    print(f"   Posts encontrados: {len(posts)}")
    for i, post in enumerate(posts[:5]):
        print(f"   [{i+1}] {post['text'][:150]}...")

    # 3. Detectar skills y capacidades
    print("\n3. Detectando menciones de skills/capacidades ...")
    detected_skills = detect_skills_from_posts(posts)
    print(f"   Skills/capacidades detectadas: {len(detected_skills)}")
    for skill in detected_skills:
        desc = skill.get("description", "")
        print(f"   - {skill['name']}" + (f" ({desc})" if desc else ""))

    # 4. Encontrar habilidades relevantes para LucidFence
    print("\n4. Filtrando skills relevantes para LucidFence ...")
    relevant_skills = find_relevant_skills_for_lucidfence(detected_skills)
    print(f"   Skills relevantes: {len(relevant_skills)}")
    for skill in relevant_skills:
        skill_path = find_skill_path(skill["name"])
        status = "disponible en ~/.hermes" if skill_path else "NO disponible localmente"
        print(f"   - {skill['name']}: {status}")

    # 5. Identificar nuevas capacidades (no skills, sino características)
    print("\n5. Identificando nuevas capacidades ...")
    new_capabilities = [s for s in detected_skills if s["name"] in [
        "batch_processing", "autonomous_delegation", "subagent",
        "kanban_plugin", "gpt5_model",
    ]]
    print(f"   Capacidades nuevas: {len(new_capabilities)}")
    for cap in new_capabilities:
        print(f"   - {cap['name']}: {cap.get('description', 'N/A')}")

    # 6. Instalar skills (si no es solo feed)
    if not args.feed_only:
        print("\n6. Instalando skills en perfiles objetivo ...")
        installed_skills = []
        not_found_skills = []
        already_installed = []

        for skill in relevant_skills:
            skill_name = skill["name"]
            skill_path = find_skill_path(skill_name)

            if skill_path is None:
                not_found_skills.append(skill_name)
                continue

            for profile in profiles:
                profile_dir = PROFILES_DIR / profile / "skills"
                # Verificar si ya está instalado
                if skill_name in get_installed_skills_in_profile(profile):
                    already_installed.append((skill_name, profile))
                    continue

                # Instalar
                success = install_skill_in_profile(skill_path, profile)
                if success:
                    installed_skills.append((skill_name, profile))
                else:
                    print(f"   Error instalando {skill_name} en {profile}")

        print(f"\n   Skills instalados: {len(installed_skills)}")
        for skill, profile in installed_skills:
            print(f"   ✓ {skill} → {profile}")

        if already_installed:
            print(f"\n   Skills ya instalados (omitidos): {len(already_installed)}")

        if not_found_skills:
            print(f"\n   Skills no encontrados en ~/.hermes: {len(not_found_skills)}")
            for skill in not_found_skills:
                print(f"   ✗ {skill}: no disponible localmente")
    else:
        installed_skills = []
        not_found_skills = []
        already_installed = []

    # 7. Resumen
    print("\n" + "=" * 70)
    print("RESUMEN DE HUGO SKILL DISCOVERY")
    print("=" * 70)
    print(f"   Feed @HermesWatcher: {'OK' if feed_text else 'ERROR'}")
    print(f"   Posts extraídos: {len(posts)}")
    print(f"   Skills detectadas: {len(detected_skills)}")
    print(f"   Skills relevantes para LucidFence: {len(relevant_skills)}")
    print(f"   Skills instalados: {len(installed_skills)}")
    print(f"   Skills ya instalados: {len(already_installed)}")
    print(f"   Skills no encontrados: {len(not_found_skills)}")
    print(f"   Nuevas capacidades: {len(new_capabilities)}")
    print("=" * 70)

    # 8. Registrar en loop log
    print("\n7. Registrando en loop-run-log.md ...")
    register_in_loop_log(
        feed_text or "",
        posts,
        detected_skills,
        installed_skills,
        new_capabilities,
    )

    # 9. Retornar código de salida
    if feed_text is None:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
