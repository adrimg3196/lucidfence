#!/usr/bin/env python3
"""
Script para Hugo (v0.15+): buscar skills/plugins nuevos en GitHub
relevantes para los agentes de LucidFence, extraerlos desde @HermesWatcher,
y registrarlos en loop-run-log.md

El script también clona repos interesantes para que los agentes los revisen.

Uso en loop:
  python3 scripts/hugo_skill_discovery.py

Con argumento para perfiles específicos:
  python3 scripts/hugo_skill_discovery.py --perfiles empresa-test-qa,empresa-cto

Solo extracción de feed (sin instalar):
  python3 scripts/hugo_skill_discovery.py --feed-only

Skills específicos:
  python3 scripts/hugo_skill_discovery.py --skills playwright-cli,playwright-component-testing
"""

import os
import sys
import re
import json
import html
import gzip
import io
import shutil
import urllib.parse
import subprocess
import argparse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from datetime import datetime

# --- Configuración ---
HERMES_WATCHER_URL = "https://x.com/HermesWatcher?s=11"
GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
GITHUB_API_TOKEN = os.environ.get("GITHUB_TOKEN", "")  # opcional, para rate limit más alto
PROFILES_DIR = Path("/Users/adri/.hermes/profiles")
HERMES_SKILLS_DIR = Path("/Users/adri/.hermes")
LUCIDFENCE_DIR = Path("/Users/adri/lucidfence")
REPO_DISCOVERY_DIR = LUCIDFENCE_DIR / "data" / "repo-discoveries"
LOG_FILE = LUCIDFENCE_DIR / "docs/internal/loop-run-log.md"
TIMESTAMP = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

# Directorio donde se clonan repos descubiertos para revisión por agentes
REPO_DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)

HERMES_WATCHER_JSON_POSTS = LUCIDFENCE_DIR / "data" / "hermeswatcher_posts.json"

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

# Palabras clave para detectar repos de GitHub relevantes en posts de X
GITHUB_REPO_KEYWORDS = [
    # Agent frameworks / autonomía
    "agent", "autonomous", "subagent", "delegation", "multi-agent", "swarm",
    # Skill/plugin systems
    "skill", "plugin", "extension", "middleware",
    # LLM/Model tooling
    "llm", "model", "gpt", "claude", "gemini", "llm-app", "inference",
    # Testing & QA
    "testing", "test", "e2e", "pytest", "playwright", "cypress",
    # DevOps & infra
    "devops", "ci", "cd", "deploy", "pipeline", "kubernetes", "docker",
    # Observability & monitoring
    "monitor", "observe", "trace", "log", "metric", "alert",
    # Security
    "security", "audit", "scan", "vulnerability", "secrets", "cve",
    # Code quality
    "lint", "format", "review", "quality", "static analysis",
    # Git & collaboration
    "git", "github", "pr", "merge", "branch", "workflow",
    # LLMs for code
    "codegen", "codestral", "starCoder", "code-Llama", "starcoder",
    # Python tooling
    "python", "pip", "poetry", "uv", "pyenv",
    # Hermes-related
    "hermes", "nous", "openclaw",
]


# ============================================================
# 1. Descarga de feed
# ============================================================

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
    """Descargar feed de HermesWatcher con manejo de gzip.

    Retorna el HTML crudo. Si hay tweets cacheados en JSON, se usan
    como fuente primaria en extract_posts.
    """
    try:
        req = Request(url, headers={"User-Agent": "HermesAgent/1.0"})
        with urlopen(req, timeout=15) as response:
            data = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
            text = data.decode("utf-8", errors="replace")
            return text
    except Exception as e:
        print(f"  Error descargando feed: {e}")
        return None


def fetch_tweet_text(tweet_id: str) -> str | None:
    """Extraer texto de un tweet específico por su ID."""
    url = f"https://x.com/i/api/graphql/.../TweetResultByRestId?variables={{\"rawData\":{{\"tweetId\":\"{tweet_id}\"}}}}"
    try:
        req = Request(url, headers={"User-Agent": "HermesAgent/1.0"})
        with urlopen(req, timeout=15) as response:
            data = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
            text = data.decode("utf-8", errors="replace")
            match = re.search(r'"fullText":"([^"]+)"', text)
            if match:
                return html.unescape(match.group(1))
            return None
    except Exception as e:
        print(f"  Error obteniendo tweet {tweet_id}: {e}")
        return None


# ============================================================
# 2. Extracción de posts (parseo HTML real de X.com)
# ============================================================

def clean_html_for_tweets(raw_html: str) -> str:
    """Limpiar el HTML eliminando bloques no visibles (script, style, meta, etc.).

    Retorna el HTML limpio listo para extraer texto de tweets.
    """
    # Eliminar bloques de script y style (incluye contenido interior)
    cleaned = re.sub(
        r'<script[^>]*>.*?</script>',
        '',
        raw_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    cleaned = re.sub(
        r'<style[^>]*>.*?</style>',
        '',
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Eliminar meta tags y link tags
    cleaned = re.sub(r'<meta[^>]*/?>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<link[^>]*/?>', '', cleaned, flags=re.IGNORECASE)
    # Eliminar atributos nonce (solo el atributo, no el contenido)
    cleaned = re.sub(r'\snonce="[^"]*"', '', cleaned, flags=re.IGNORECASE)
    # Eliminar scripts específicos de X.com que inyectan ruido
    cleaned = re.sub(
        r'<script[^>]*id="_R_"[^>]*>.*?</script>',
        '',
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return cleaned


def extract_tweets_from_html(raw_html: str) -> list[dict]:
    """Extraer tweets del HTML de X.com buscando patrones de tweet text.

    Primero limpia el HTML eliminando script/style/meta/link/nonce
    para evitar extraer contenido no visible.
    """
    cleaned = clean_html_for_tweets(raw_html)
    tweets: list[dict] = []

    # Patrón 1: tweets en data-testid="tweetText" (el más específico)
    # Usamos triple-quoted raw string para poder incluir " y ' sin escaping
    tweet_text_re = re.compile(
        r"""data-testid=["'][^"']*tweetText[^"']*["'][^>]*>([^<]+)<""",
        re.IGNORECASE,
    )
    for match in tweet_text_re.finditer(cleaned):
        text = html.unescape(match.group(1).strip())
        if text and len(text) > 15 and not text.startswith("{") and not text.startswith("<"):
            tweets.append({"text": text})
        if len(tweets) >= 10:
            return tweets[:10]

    # Patrón 2: div con clase tweet-text-content
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
            if clean and len(clean) > 15 and not clean.startswith("{") and not clean.startswith("<"):
                tweets.append({"text": clean})
            if len(tweets) >= 10:
                return tweets[:10]

    # Patrón 3: meta description (último recurso)
    if len(tweets) < 1:
        meta_desc_re = re.compile(
            r"""<meta[^>]*name=["']twitter:description["'][^>]*content=["']([^"']+)["']""",
            re.IGNORECASE,
        )
        for match in meta_desc_re.finditer(raw_html):
            text = html.unescape(match.group(1).strip())
            if text and len(text) > 15:
                tweets.append({"text": text})
                break  # Solo el primero

    # Patrón 4: bloques data-testid con tweet (amplio)
    if len(tweets) < 3:
        content_re = re.compile(
            r"""<div[^>]*data-testid=["'][^"']*tweet[^"']*["'][^>]*>(.*?)</div>""",
            re.DOTALL | re.IGNORECASE,
        )
        for match in content_re.finditer(cleaned):
            clean = re.sub(r"<[^>]+>", " ", match.group(1))
            clean = html.unescape(clean).strip()
            clean = re.sub(r"\s+", " ", clean)
            if clean and len(clean) > 20 and not clean.startswith("{") and not clean.startswith("<"):
                tweets.append({"text": clean})
            if len(tweets) >= 10:
                return tweets[:10]

    return tweets[:10]


def extract_posts_fallback(raw_text: str) -> list[dict]:
    """Heurística fallback: extraer fragmentos de texto que parezcan posts.

    Exclusión estricta de líneas que parezcan código/CSS/JS/meta tags.
    """
    posts: list[dict] = []
    seen_texts: set[str] = set()

    # Prefixos que indican que no es un tweet real
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
        # Omitir líneas que parezcan código o etiquetas
        if line.startswith(skip_prefixes):
            continue
        if re.match(r'^\s*$', line):
            continue
        if re.match(r'^[\w]+:[;,{}$\'"\']', line):
            continue
        clean = re.sub(r'\s+', ' ', line).strip()
        clean = html.unescape(clean)
        if clean and clean not in seen_texts and len(clean) > 45:
            seen_texts.add(clean)
            posts.append({"text": clean})

    return posts[:10]


def extract_posts(feed_text: str) -> list[dict]:
    """Extraer los posts más recientes del feed de HermesWatcher.

    Prioridad:
    1. Tweets cacheados desde JSON (browser_exec)
    2. HTML parsing de X.com (limitado, solo bio + etiquetas)
    """
    posts: list[dict] = []

    # 1. Intentar usar tweets cacheados desde JSON (fuente primaria)
    json_tweets = load_json_posts()
    if json_tweets:
        for tweet_text in json_tweets:
            if tweet_text and tweet_text not in [p["text"] for p in posts]:
                posts.append({"text": tweet_text})
        # Si tenemos tweets del JSON, devolvemos esos (no intentamos HTML)
        if posts:
            print(f"   Usando {len(posts)} tweets desde JSON cacheado")
            return posts[:10]

    # 2. Fallback: parsear HTML de X.com (solo bio, etiquetas, etc.)
    html_posts = extract_tweets_from_html(feed_text)
    for hp in html_posts:
        if hp["text"] and hp["text"] not in [p["text"] for p in posts]:
            posts.append(hp)

    if len(posts) < 3:
        fb_posts = extract_posts_fallback(feed_text)
        for fp in fb_posts:
            if fp["text"] and fp["text"] not in [p["text"] for p in posts]:
                posts.append(fp)

    return posts[:10]


# ============================================================
# 3. Detección de skills en posts
# ============================================================

def detect_skills_from_posts(posts: list[dict]) -> list[dict]:
    """Buscar menciones de skills/plugins/capacidades en los posts.

    Retorna lista de dicts con:
        name: nombre normalizado de la skill/capacidad
        description: fragmento del post donde aparece
        source: 'post' (detectado en feed)
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
                        "description": text[:200],
                        "source": "post",
                    })

    return detected


# Palabras clave para detectar skills/capacidades mencionadas en X
SKILL_KEYWORDS = [
    # Skills de Hermes
    "playwright-cli",
    "playwright-component-testing",
    "playwrighttrace",
    "playwright-test-runner",
    # Capacidades de Hermes
    "batch_processing",
    "autonomous_delegation",
    "subagent",
    "kanban_plugin",
    "gpt5_model",
    "web-search",
    "web-extract",
    "image-generate",
    "text-to-speech",
    "browser-exec",
    "cronjob",
    "delegate-task",
    "skill-view",
    "skill-manage",
    "clarify",
    "computer-use",
    "memory",
    "session-search",
    "lucidfence",
    "hermestool",
    "telegram",
    "apple-notes",
    "apple-reminders",
    "find-my",
    "imessage",
    "openai-whisper",
    "whisper",
    "qdrant",
    "milvus",
    "chromadb",
    "knowledge-graph",
    "graphify",
    "llm-wiki",
    "arxiv",
    "google-workspace",
    "notion",
    "airtable",
    "box",
    "himalaya",
    "xurl",
    "open-hue",
    "obsidian",
    "meeting-action-items",
    "document-to-action-items",
    "weekly-review-planning",
    "session-librarian",
    "product-price-monitor",
    "ocr-and-documents",
    "nano-pdf",
    "pdf",
    "docx",
    "xlsx",
    "powerpoint",
    "maps",
    "blocked-page-recovery",
    "grill-me",
    "test-driven-development",
    "systematic-debugging",
    "codebase-inspection",
]


# ============================================================
# 4. Encontrar skills relevantes para LucidFence
# ============================================================

def find_skill_path(skill_name: str) -> Path | None:
    """Buscar la ruta de un skill en ~/.hermes."""
    for category_dir in HERMES_SKILLS_DIR.iterdir():
        if not category_dir.is_dir():
            continue
        for skill_dir in category_dir.iterdir():
            if skill_dir.is_dir() and skill_dir.name == skill_name:
                return skill_dir
            # También buscar con guion bajo
            if skill_dir.is_dir() and skill_dir.name.replace("_", "-") == skill_name:
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


def get_installed_skills_per_profile() -> dict[str, list[str]]:
    """Retornar dict {profile: [skills]} para todos los perfiles."""
    result: dict[str, list[str]] = {}
    for profile_dir in PROFILES_DIR.iterdir():
        if profile_dir.is_dir():
            profile_name = profile_dir.name
            skills = get_installed_skills_in_profile(profile_name)
            result[profile_name] = skills
    return result


def find_relevant_skills_for_lucidfence(
    detected_skills: list[dict],
) -> list[dict]:
    """Filtrar skills detectadas para los que son relevantes para LucidFence.

    Se enfoca en skills que:
    - Ayuden a los agentes a trabajar mejor el repo
    - Sean herramientas de desarrollo/test/QA/security/observabilidad
    - Sean plugins que los agentes puedan instalar en sus perfiles
    """
    relevant: list[dict] = []
    lucifence_keywords = [
        "playwright", "testing", "test", "e2e", "cypress",
        "pytest", "python", "lint", "format",
        "security", "audit", "scan", "vulnerability",
        "git", "github", "pr", "review", "merge",
        "ci", "cd", "deploy", "pipeline",
        "monitor", "observe", "trace", "log", "metric",
        "agent", "autonomous", "subagent", "delegation",
        "skill", "plugin", "extension",
        "llm", "model", "claude", "gpt",
        "kanban", "planning",
        "brain", "memory", "context",
        "hermes", "nous",
    ]

    for skill in detected_skills:
        skill_name = skill["name"]
        # Verificar si existe localmente como skill
        skill_path = find_skill_path(skill_name.replace("_", "-"))

        for keyword in lucifence_keywords:
            if keyword in skill_name.lower():
                if skill_path is not None:
                    # Skill disponible localmente — relevante
                    relevant.append(skill)
                else:
                    # Skill mencionada pero no disponible — aún así la incluimos
                    # para registro (podría ser algo que vendrán en futuro)
                    relevant.append(skill)
                break
        else:
            # Si no hay keyword match pero existe el skill,
            # asumimos que podría ser relevante (no descartamos)
            if skill_path is not None:
                relevant.append(skill)

    return relevant


# ============================================================
# 5. Descubrimiento de repos de GitHub
# ============================================================

def extract_github_urls_from_posts(posts: list[dict]) -> list[dict]:
    """Extraer URLs de GitHub mencionadas en los posts."""
    urls: list[dict] = []
    url_pattern = re.compile(
        r'https?://(?:www\.)?github\.com/([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)',
        re.IGNORECASE,
    )

    for post in posts:
        text = post.get("text", "")
        matches = url_pattern.finditer(text)
        for match in matches:
            full_name = match.group(1)
            start = match.start()
            context_start = max(0, start - 100)
            context_end = min(len(text), start + len(match.group(0)) + 100)
            snippet = text[context_start:context_end].strip()
            urls.append({
                "url": f"https://github.com/{full_name}",
                "full_name": full_name,
                "description": snippet,
            })

    return urls


def normalize_github_full_name(url: str) -> str | None:
    """Extraer nombre completo (owner/repo) de una URL de GitHub."""
    match = re.search(
        r'github\.com/([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)',
        url,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


def search_github_repos(keyword: str) -> list[dict]:
    """Buscar repos en GitHub API por keyword.

    Retorna lista de repos ordenados por stars (desc).
    """
    if not keyword:
        return []

    query_parts = [
        f"{keyword}",
        "stars:>=10",
        "pushed:>2024-01-01",
        "-fork",
    ]
    query = " ".join(query_parts)

    headers: dict[str, str] = {}
    if GITHUB_API_TOKEN:
        headers["Authorization"] = f"token {GITHUB_API_TOKEN}"

    params = urllib.parse.urlencode({
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": "10",
    })

    url = f"{GITHUB_SEARCH_API}?{params}"

    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        items = data.get("items", [])
        result: list[dict] = []
        for item in items:
            result.append({
                "full_name": item.get("full_name", ""),
                "html_url": item.get("html_url", ""),
                "description": item.get("description", "") or "",
                "language": item.get("language"),
                "stargazers_count": item.get("stargazers_count", 0),
                "forks_count": item.get("forks_count", 0),
                "topics": item.get("topics", []),
                "updated_at": item.get("updated_at", ""),
            })
        return result

    except Exception as e:
        print(f"      Error buscando '{keyword}': {e}")
        return []


def discover_github_repos(
    posts: list[dict],
    feed_text: str,
) -> list[dict]:
    """Buscar repos de GitHub relevantes para los agentes de LucidFence.

    Busca en dos fuentes:
    1. Menciones de repos en los posts de @HermesWatcher (extrayendo URLs)
    2. Búsqueda en GitHub API con keywords relevantes

    Retorna lista de dicts con:
        full_name, description, language, url, stars, fork_count, topic_tags
    """
    repos: list[dict] = []
    seen: set[str] = set()

    # 1. Extraer URLs de GitHub de los posts
    print("   8a. Extrayendo URLs de GitHub de los posts ...")
    post_urls = extract_github_urls_from_posts(posts)
    for url_data in post_urls:
        full_name = normalize_github_full_name(url_data["url"])
        if full_name and full_name not in seen:
            seen.add(full_name)
            repos.append({
                "full_name": full_name,
                "url": url_data["url"],
                "source": "post_mention",
                "description": url_data.get("description", ""),
                "language": None,
                "stars": 0,
                "fork_count": 0,
                "topic_tags": [],
            })

    # 2. Búsqueda en GitHub API con keywords
    print("   8b. Buscando en GitHub API con keywords relevantes ...")
    for keyword in GITHUB_REPO_KEYWORDS[:8]:
        keyword_repos = search_github_repos(keyword)
        for repo_data in keyword_repos:
            full_name = repo_data["full_name"]
            if full_name not in seen:
                seen.add(full_name)
                repos.append({
                    "full_name": full_name,
                    "url": repo_data["html_url"],
                    "source": "github_search",
                    "description": repo_data.get("description", "") or "",
                    "language": repo_data.get("language"),
                    "stars": repo_data.get("stargazers_count", 0),
                    "fork_count": repo_data.get("forks_count", 0),
                    "topic_tags": repo_data.get("topics", []),
                })
        if len(repos) >= 30:
            break

    repos.sort(key=lambda r: r.get("stars", 0), reverse=True)
    return repos


def clone_new_repos(repos: list[dict]) -> list[Path]:
    """Clonar repos nuevos para que los agentes los revisen.

    Solo clona repos que no existan ya en el directorio de descubrimientos.
    Retorna lista de Paths de los repos clonados.
    """
    cloned: list[Path] = []

    for repo in repos:
        full_name = repo["full_name"]
        repo_dir = REPO_DISCOVERY_DIR / full_name.replace("/", "_")

        if repo_dir.exists():
            continue

        print(f"      Clonando {full_name} ...")
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo["url"], str(repo_dir)],
                check=True,
                capture_output=True,
                timeout=30,
            )
            cloned.append(repo_dir)
            print(f"      ✓ Clonado en {repo_dir}")
        except Exception as e:
            print(f"      ✗ Error clonando {full_name}: {e}")

    return cloned


# ============================================================
# 6. Registro en loop log
# ============================================================

def register_in_loop_log(
    feed_text: str,
    posts: list[dict],
    detected_skills: list[dict],
    installed_skills: list[tuple[str, str]],
    new_capabilities: list[dict],
    github_repos: list[dict] | None = None,
    cloned_repos: list[Path] | None = None,
) -> None:
    """Registrar la ejecución del skill discovery en loop-run-log.md."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    skill_names = [s["name"] for s in detected_skills]
    installed_desc = ", ".join(
        f"{s}→{p}" for s, p in installed_skills
    ) if installed_skills else "ninguno"

    cap_names = [c["name"] for c in new_capabilities]

    github_summary = ""
    if github_repos:
        top_repos = github_repos[:5]
        repo_lines = []
        for r in top_repos:
            desc = (r.get("description") or "")[:80]
            repo_lines.append(f"{r['full_name']} ({r.get('language', 'N/A')}) — {desc}")
        github_summary = "Repos GitHub: " + "; ".join(repo_lines)
        if cloned_repos:
            cloned_names = [p.name.replace("_", "/") for p in cloned_repos]
            github_summary += f" | Clonados: {', '.join(cloned_names)}"

    entry = (
        f"- {TIMESTAMP} | L2 | Skill discovery (automejora) | "
        f"Feed @HermesWatcher consultado. "
        f"Posts relevantes: {len(posts)}. "
        f"Skills detectadas: {', '.join(skill_names) if skill_names else 'ninguna'}. "
        f"Skills instalados: {installed_desc}. "
        f"Capacidades nuevas detectadas: {', '.join(cap_names) if cap_names else 'ninguna'}. "
        f"{github_summary}. "
        f"Acción: instalar skills descubiertos en perfiles clave + clones para revisión de agentes."
    )

    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")

    print(f"Registrado en {LOG_FILE}")


# ============================================================
# 7. Main
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Buscar y instalar skills nuevos desde @HermesWatcher",
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
        help="Solo extraer y mostrar el feed, sin instalar nada",
    )
    parser.add_argument(
        "--skills",
        type=str,
        default=None,
        help="Lista comma-separated de skills específicos a instalar",
    )
    parser.add_argument(
        "--no-clone",
        action="store_true",
        help="Saltar clonado de repos (solo descubrir y mostrar)",
    )

    args = parser.parse_args()

    if args.perfiles:
        profiles = [p.strip() for p in args.perfiles.split(",")]
    else:
        profiles = DEFAULT_PROFILES

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
                profile_dir = PROFILES_DIR / profile / "skills"
                if skill_name in get_installed_skills_in_profile(profile):
                    already_installed.append((skill_name, profile))
                    continue

                success = install_skill_in_profile(skill_path, profile)
                if success:
                    installed_skills.append((skill_name, profile))
                else:
                    print(f"   Error instalando {skill_name} en {profile}")
    else:
        installed_skills = []
        not_found_skills = []
        already_installed = []

    # 8. Descubrir repos de GitHub relevantes
    print("\n8. Buscando repos de GitHub relevantes para los agentes ...")
    github_repos = discover_github_repos(posts, feed_text)
    print(f"   Repos de GitHub detectados: {len(github_repos)}")
    for repo in github_repos[:5]:
        print(f"   - {repo['full_name']} ({repo['language'] or 'N/A'}) — {repo.get('description', 'N/A')[:100]}")

    # 9. Clonar repos nuevos para revisión por agentes (opcional)
    if not args.no_clone:
        print("\n9. Clonando repos nuevos para revisión por agentes ...")
        cloned_repos = clone_new_repos(github_repos)
        print(f"   Repos clonados: {len(cloned_repos)}")
        for repo_path in cloned_repos[:5]:
            print(f"   ✓ {repo_path}")
    else:
        cloned_repos = []
        print("\n9. Clonado skipped (--no-clone)")

    # 10. Resumen
    print("\n" + "=" * 70)
    print("RESUMEN DE HUGO SKILL DISCOVERY (con GitHub repos)")
    print("=" * 70)
    print(f"   Feed @HermesWatcher: {'OK' if feed_text else 'ERROR'}")
    print(f"   Posts extraídos: {len(posts)}")
    print(f"   Skills detectadas: {len(detected_skills)}")
    print(f"   Skills relevantes para LucidFence: {len(relevant_skills)}")
    print(f"   Skills instalados: {len(installed_skills)}")
    print(f"   Skills ya instalados: {len(already_installed)}")
    print(f"   Skills no encontrados: {len(not_found_skills)}")
    print(f"   Nuevas capacidades: {len(new_capabilities)}")
    print(f"   Repos de GitHub detectados: {len(github_repos)}")
    print(f"   Repos clonados para revisión: {len(cloned_repos)}")
    print("=" * 70)

    # 11. Registrar en loop log
    print("\n11. Registrando en loop-run-log.md ...")
    register_in_loop_log(
        feed_text or "",
        posts,
        detected_skills,
        installed_skills,
        new_capabilities,
        github_repos=github_repos,
        cloned_repos=cloned_repos,
    )

    if feed_text is None:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
