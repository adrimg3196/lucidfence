#!/usr/bin/env python3
"""
Script para Hugo (v0.15+): buscar skills/plugins/capacidades nuevos
en @HermesWatcher y registrarlos en loop-run-log.md

Solo fuente: feed de @HermesWatcher (Nitter caído, X renderiza tweets vía JS).
Los tweets reales se cachejan vía browser_exec en data/hermeswatcher_posts.json.

NO busca repos de GitHub — es ruido que no aporta valor a los agentes.
"""

import os
import sys
import re
import json
import html
import gzip
import shutil
import argparse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
from datetime import datetime

# --- Configuración ---
HERMES_WATCHER_URL = "https://x.com/HermesWatcher?s=11"
HERMES_WATCHER_JSON_POSTS = Path("/Users/adri/lucidfence/data/hermeswatcher_posts.json")
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

# Keywords para detectar skills/capacidades mencionadas en X
SKILL_KEYWORDS = [
    # Capacidades de Hermes (estas sí aportan valor)
    "subagent",
    "batch_processing",
    "autonomous_delegation",
    "memory",
    "kanban_plugin",
    "gpt5_model",
    # Tooling
    "web-search", "web-extract", "image-generate", "text-to-speech",
    "browser-exec", "cronjob", "delegate-task",
    "skill-view", "skill-manage", "clarify", "computer-use",
    "session-search", "lucidfence", "hermestool", "telegram",
    # Skills existentes
    "playwright-cli", "playwright-component-testing", "playwrighttrace",
    "grill-me", "test-driven-development", "systematic-debugging",
    "codebase-inspection", "dogfood", "spike", "plan",
    "simplify-code", "requesting-code-review", "python-debugpy",
    "node-inspect-debugger", "inspecting-hermes-desktop-dom",
    "hermes-agent-skill-authoring", "merge-reconciler",
    # Skills externos útiles
    "arxiv", "llm-wiki", "knowledge-graph", "graphify",
    "google-workspace", "notion", "airtable", "box",
    "obsidian", "meeting-action-items", "weekly-review-planning",
    "session-librarian", "product-price-monitor",
    "ocr-and-documents", "nano-pdf", "pdf", "docx", "xlsx",
    "powerpoint", "maps", "blocked-page-recovery",
    "apple-notes", "apple-reminders", "find-my", "imessage",
    "open-hue", "himalaya", "xurl",
    "huggingface-hub", "weights-and-biases", "evaluating-llms-harness",
    # Testing
    "pytest", "playwright", "cypress", "test", "e2e", "testing",
]


def load_json_posts() -> list[str] | None:
    """Cargar tweets cacheados desde JSON (generado por browser_exec)."""
    if not HERMES_WATCHER_JSON_POSTS.exists():
        return None
    try:
        data = json.loads(HERMES_WATCHER_JSON_POSTS.read_text())
        tweets = data.get("tweets", [])
        if tweets:
            print(f"   Cargados {len(tweets)} tweets desde JSON cacheado")
            return tweets
    except Exception as e:
        print(f"   Error leyendo JSON de tweets: {e}")
    return None


def fetch_feed(url: str) -> str | None:
    """Descargar HTML de X.com (solo para fallback, no contiene tweets reales)."""
    try:
        req = Request(url, headers={"User-Agent": "HermesAgent/1.0"})
        with urlopen(req, timeout=15) as response:
            data = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
            return data.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  Error descargando feed: {e}")
        return None


# ============================================================
# Extracción de tweets desde HTML (solo fallback)
# ============================================================

def clean_html_for_tweets(raw_html: str) -> str:
    """Limpiar el HTML eliminando bloques no visibles."""
    cleaned = re.sub(r'<script[^>]*>.*?</script>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<style[^>]*>.*?</style>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<meta[^>]*/?>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<link[^>]*/?>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\snonce="[^"]*"', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<script[^>]*id="_R_"[^>]*>.*?</script>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    return cleaned


def extract_tweets_from_html(raw_html: str) -> list[dict]:
    """Extraer tweets del HTML de X.com buscando patrones de tweet text.

    NOTA: X renderiza tweets vía JS, el HTML estático solo tiene el bio.
    Este método es solo fallback cuando no hay JSON cacheado.
    """
    cleaned = clean_html_for_tweets(raw_html)
    tweets: list[dict] = []

    # data-testid="tweetText"
    tweet_text_re = re.compile(
        r"""data-testid=["'][^"']*tweetText[^"']*["'][^>]*>([^<]+)<""",
        re.IGNORECASE,
    )
    for match in tweet_text_re.finditer(cleaned):
        text = html.unescape(match.group(1).strip())
        if text and len(text) > 15:
            tweets.append({"text": text})
        if len(tweets) >= 10:
            return tweets[:10]

    # div con clase tweet-text
    if len(tweets) < 3:
        tweet_div_re = re.compile(
            r"""<div[^>]*class=["'][^"']*tweet-text[^"']*["'][^>]*>(.*?)</div>""",
            re.DOTALL | re.IGNORECASE,
        )
        for match in tweet_div_re.finditer(cleaned):
            raw = match.group(1)
            clean = re.sub(r"<[^>]+>", " ", raw)
            clean = html.unescape(clean).strip()
            clean = re.sub(r"\s+", " ", clean)
            if clean and len(clean) > 15:
                tweets.append({"text": clean})
            if len(tweets) >= 10:
                return tweets[:10]

    # meta description
    if len(tweets) < 1:
        meta_desc_re = re.compile(
            r"""<meta[^>]*name=["']twitter:description["'][^>]*content=["']([^"']+)["']""",
            re.IGNORECASE,
        )
        for match in meta_desc_re.finditer(raw_html):
            text = html.unescape(match.group(1).strip())
            if text and len(text) > 15:
                tweets.append({"text": text})
                break

    return tweets[:10]


def extract_posts_fallback(raw_text: str) -> list[dict]:
    """Heurística fallback: extraer fragmentos de texto que parezcan posts."""
    posts: list[dict] = []
    seen_texts: set[str] = set()

    skip_prefixes = (
        '<', '{', '[', ' ', ';', '}', ')', '(',
        'Chrome', 'Mozilla', 'Safari', 'AppleWebKit',
        'href', 'src', 'import', 'script', 'style',
        'meta', 'link', 'div', 'class', 'id',
        'data-', 'nonce', 'cookie', 'window',
        'document', 'var ', 'function', 'const ', 'let ',
        'body', 'head', 'html', 'title', 'lang',
        'utf', 'viewport', 'robots', 'description',
    )

    for line in raw_text.splitlines():
        line = line.strip()
        if len(line) <= 30:
            continue
        if line.startswith(skip_prefixes):
            continue
        if re.match(r'^\s*$', line):
            continue
        if re.match(r'^[\w]+:[;,{}$\'"]', line):
            continue
        clean = re.sub(r'\s+', ' ', line).strip()
        clean = html.unescape(clean)
        if clean and clean not in seen_texts and len(clean) > 45:
            seen_texts.add(clean)
            posts.append({"text": clean})

    return posts[:10]


def extract_posts(feed_text: str) -> list[dict]:
    """Extraer los posts más recientes de @HermesWatcher.

    Prioridad:
    1. Tweets cacheados desde JSON (browser_exec) — fuente primaria
    2. HTML parsing de X.com (solo bio) — fallback
    """
    posts: list[dict] = []

    # 1. JSON cacheado (fuente primaria)
    json_tweets = load_json_posts()
    if json_tweets:
        for tweet_text in json_tweets:
            if tweet_text and tweet_text not in [p["text"] for p in posts]:
                posts.append({"text": tweet_text})
        if posts:
            print(f"   Usando {len(posts)} tweets desde JSON cacheado")
            return posts[:10]

    # 2. Fallback HTML
    for hp in extract_tweets_from_html(feed_text):
        if hp["text"] and hp["text"] not in [p["text"] for p in posts]:
            posts.append(hp)

    if len(posts) < 3:
        for fp in extract_posts_fallback(feed_text):
            if fp["text"] and fp["text"] not in [p["text"] for p in posts]:
                posts.append(fp)

    return posts[:10]


# ============================================================
# Detección de skills en posts
# ============================================================

def detect_skills_from_posts(posts: list[dict]) -> list[dict]:
    """Buscar menciones de skills/capacidades en los posts de @HermesWatcher.

    Retorna lista de dicts con:
        name: nombre normalizado
        description: fragmento del post donde aparece
        source: 'post'
    """
    detected: list[dict] = []
    seen: set[str] = set()

    for post in posts:
        text = post.get("text", "")
        lower_text = text.lower()

        for keyword in SKILL_KEYWORDS:
            if keyword in lower_text:
                name = keyword.lower().replace("-", "_").replace(" ", "_")
                if name not in seen:
                    seen.add(name)
                    detected.append({
                        "name": name,
                        "description": text[:300],
                        "source": "post",
                    })

    return detected


# ============================================================
# Encontrar skills relevantes para LucidFence
# ============================================================

def find_skill_path(skill_name: str) -> Path | None:
    """Buscar la ruta de un skill en ~/.hermes."""
    for category_dir in HERMES_SKILLS_DIR.iterdir():
        if not category_dir.is_dir():
            continue
        for skill_dir in category_dir.iterdir():
            if skill_dir.is_dir():
                if skill_dir.name == skill_name:
                    return skill_dir
                if skill_dir.name.replace("_", "-") == skill_name:
                    return skill_dir
    return None


def get_installed_skills_in_profile(profile: str) -> list[str]:
    """Listar skills instalados en un perfil."""
    profile_dir = PROFILES_DIR / profile / "skills"
    if not profile_dir.exists():
        return []
    return [d.name for d in profile_dir.iterdir() if d.is_dir()]


def install_skill_in_profile(skill_path: Path, profile: str) -> bool:
    """Copiar un skill a la carpeta de skills de un perfil."""
    dest_dir = PROFILES_DIR / profile / "skills" / skill_path.name
    try:
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(skill_path, dest_dir)
        print(f"      Instalado: {skill_path.name} → {profile}")
        return True
    except Exception as e:
        print(f"      Error instalando {skill_path.name} en {profile}: {e}")
        return False


def find_relevant_skills_for_lucidfence(
    detected_skills: list[dict],
) -> list[dict]:
    """Filtrar skills detectadas para los que son relevantes para LucidFence."""
    relevant: list[dict] = []
    lucifence_keywords = [
        "subagent", "batch", "autonomous", "memory", "kanban",
        "playwright", "testing", "test", "e2e", "cypress",
        "pytest", "security", "audit", "scan", "vulnerability",
        "git", "github", "pr", "review", "merge",
        "ci", "cd", "deploy", "pipeline",
        "monitor", "observe", "trace", "log", "metric",
        "agent", "delegation", "skill", "plugin", "extension",
        "llm", "model", "claude", "gpt",
        "brain", "context", "hermes", "nous",
        "lucidfence", "web-search", "web-extract",
        "browser-exec", "cronjob", "delegate-task",
    ]

    for skill in detected_skills:
        skill_name = skill["name"]
        skill_path = find_skill_path(skill_name.replace("_", "-"))

        for keyword in lucifence_keywords:
            if keyword in skill_name.lower():
                relevant.append(skill)
                break
        else:
            if skill_path is not None:
                relevant.append(skill)

    return relevant


# ============================================================
# Registro en loop log
# ============================================================

def register_in_loop_log(
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
        f"- {TIMESTAMP} | L2 | Skill discovery (@HermesWatcher) | "
        f"Posts: {len(posts)}. "
        f"Skills detectadas: {', '.join(skill_names) if skill_names else 'ninguna'}. "
        f"Skills instalados: {installed_desc}. "
        f"Capacidades nuevas: {', '.join(cap_names) if cap_names else 'ninguna'}. "
        f"Sin búsqueda GitHub (ruido). "
        f"Acción: usar capacidades detectadas en los agentes."
    )

    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")

    print(f"Registrado en {LOG_FILE}")


# ============================================================
# Main
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Buscar skills/capacidades nuevos desde @HermesWatcher",
    )
    parser.add_argument(
        "--perfiles",
        type=str,
        default=None,
        help="Lista comma-separated de perfiles para instalar skills",
    )
    parser.add_argument(
        "--feed-only",
        action="store_true",
        help="Solo mostrar posts detectados, sin detección de skills",
    )

    args = parser.parse_args()

    if args.perfiles:
        profiles = [p.strip() for p in args.perfiles.split(",")]
    else:
        profiles = DEFAULT_PROFILES

    print("=" * 70)
    print("HUGO: Skill Discovery — @HermesWatcher (sin GitHub)")
    print("=" * 70)

    # 1. Descargar feed (solo para fallback)
    print(f"\n[TIMESTAMP] {TIMESTAMP}")
    print("\n1. Descargando fallback HTML de @HermesWatcher ...")
    feed_text = fetch_feed(HERMES_WATCHER_URL)

    if feed_text is None:
        print("   Advertencia: no se pudo descargar HTML, usando solo JSON cacheado")
        feed_text = ""

    if feed_text:
        print(f"   OK: {len(feed_text)} chars (solo se usa si no hay JSON cacheado)")

    # 2. Extraer posts
    print("\n2. Extrayendo posts de @HermesWatcher ...")
    posts = extract_posts(feed_text)
    print(f"   Posts encontrados: {len(posts)}")
    for i, post in enumerate(posts[:5]):
        print(f"   [{i+1}] {post['text'][:150]}...")

    if args.feed_only:
        print("\n(Solo feed — detección de skills omitida por --feed-only)")
        return 0

    # 3. Detectar skills y capacidades
    print("\n3. Detectando menciones de skills/capacidades ...")
    detected_skills = detect_skills_from_posts(posts)
    print(f"   Skills/capacidades detectadas: {len(detected_skills)}")
    for skill in detected_skills:
        desc = skill.get("description", "")
        print(f"   - {skill['name']}" + (f" ({desc[:80]}...)" if desc else ""))

    # 4. Encontrar habilidades relevantes para LucidFence
    print("\n4. Filtrando skills relevantes para LucidFence ...")
    relevant_skills = find_relevant_skills_for_lucidfence(detected_skills)
    print(f"   Skills relevantes: {len(relevant_skills)}")
    for skill in relevant_skills:
        skill_path = find_skill_path(skill["name"])
        status = "disponible en ~/.hermes" if skill_path else "NO es skill descargable (capacidad de plataforma)"
        print(f"   - {skill['name']}: {status}")

    # 5. Identificar nuevas capacidades
    print("\n5. Identificando nuevas capacidades ...")
    new_capabilities = [s for s in detected_skills if s["name"] in [
        "batch_processing", "autonomous_delegation", "subagent",
        "kanban_plugin", "gpt5_model", "memory",
    ]]
    print(f"   Capacidades nuevas: {len(new_capabilities)}")
    for cap in new_capabilities:
        print(f"   - {cap['name']}: {cap.get('description', 'N/A')[:120]}")

    # 6. Instalar skills (si no es solo feed)
    if not args.feed_only:
        print("\n6. Instalando skills en perfiles objetivo ...")
        installed_skills: list[tuple[str, str]] = []
        not_found_skills: list[str] = []
        already_installed: list[tuple[str, str]] = []

        for skill in relevant_skills:
            skill_name = skill["name"]
            skill_path = find_skill_path(skill_name)

            if skill_path is None:
                not_found_skills.append(skill_name)
                continue

            for profile in profiles:
                if skill_name in get_installed_skills_in_profile(profile):
                    already_installed.append((skill_name, profile))
                    continue

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
            print(f"\n   Skills no encontrados (capacidades de plataforma, no skills): {len(not_found_skills)}")
            for skill in not_found_skills:
                print(f"   - {skill}")
    else:
        installed_skills = []
        not_found_skills = []
        already_installed = []

    # 7. Resumen
    print("\n" + "=" * 70)
    print("RESUMEN DE HUGO SKILL DISCOVERY (solo @HermesWatcher)")
    print("=" * 70)
    print(f"   Posts extraídos: {len(posts)}")
    print(f"   Skills detectadas: {len(detected_skills)}")
    print(f"   Skills relevantes: {len(relevant_skills)}")
    print(f"   Skills instalados: {len(installed_skills)}")
    print(f"   Skills ya instalados: {len(already_installed)}")
    print(f"   Skills no encontrados (capacidades): {len(not_found_skills)}")
    print(f"   Nuevas capacidades: {len(new_capabilities)}")
    print("   GitHub repos: N/A (excluido — ruido sin valor)")
    print("=" * 70)

    # 8. Registrar en loop log
    print("\n8. Registrando en loop-run-log.md ...")
    register_in_loop_log(
        posts,
        detected_skills,
        installed_skills,
        new_capabilities,
    )

    if feed_text is None and not load_json_posts():
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
