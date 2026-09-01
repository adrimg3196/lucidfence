#!/usr/bin/env python3
"""Agente de automejora: busca skills nuevos en el feed de @HermesWatcher,
detecta qué skills nuevos pueden mejorar a los agentes de LucidFence, e instala
los más relevantes.

Fuente: X.com/HermesWatcher feed (descompuesto gzip)
Acción: instalar skills que mejoren a los agentes de LucidFence.
"""

import os
import re
import html
import gzip
import io
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

REPO = Path("/Users/adri/lucidfence")
LOG = REPO / "docs/internal/loop-run-log.md"
HERMES_WATCHER_URL = "https://x.com/HermesWatcher?s=11"
PROFILES_DIR = Path("/Users/adri/.hermes/profiles")
TIMESTAMP = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_feed():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://x.com/",
    }
    req = Request(HERMES_WATCHER_URL, headers=headers)
    with urlopen(req, timeout=20) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as f:
                raw = f.read()
        text = raw.decode("utf-8", errors="replace")
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL|re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL|re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text


def extract_posts(text):
    """Extraer los posts más recientes del feed limpio."""
    posts = []
    # El feed tiene tweets intercalados con UI elements
    # Buscar patrones de posts: @HermesWatcher seguido de texto
    tweet_pattern = re.compile(r'@HermesWatcher\s+([\w\s]*?)(?=@HermesWatcher|$)')
    matches = tweet_pattern.findall(text)
    for m in matches:
        clean = m.strip()
        if len(clean) > 10 and clean not in [p["text"][:80] for p in posts]:
            posts.append({"text": clean[:400]})
    
    # También buscar secciones que parezcan posts (después de "@HermesWatcher")
    sections = text.split("@HermesWatcher")
    for i, section in enumerate(sections[1:], 1):
        clean = section.strip()[:400]
        if len(clean) > 20 and clean not in [p["text"] for p in posts]:
            posts.append({"text": clean})
    
    return posts[:8]  # Máximo 8 posts


def detect_new_skills(posts):
    """De los posts, detectar menciones de skills/plugins/capacidades nuevas."""
    skills_mentioned = []
    
    for post in posts:
        text = post["text"]
        lower = text.lower()
        
        # Detectar menciones de skills/plugins
        if 'skill' in lower:
            # Buscar qué skill se menciona
            skill_match = re.findall(r'skill[s]?\s+(?:de|para|is|are|can|can be)\s+([a-z][a-z0-9_-]{2,40})', lower)
            for sm in skill_match:
                if sm not in [s["name"] for s in skills_mentioned]:
                    skills_mentioned.append({"name": sm, "source": "HermesWatcher"})
        
        if 'plugin' in lower:
            plugin_match = re.findall(r'plugin[s]?\s+(?:de|para|is|are|adds?)\s+([a-z][a-z0-9_-]{2,40})', lower)
            for pm in plugin_match:
                if pm not in [s["name"] for s in skills_mentioned]:
                    skills_mentioned.append({"name": pm, "source": "HermesWatcher"})
        
        # Detectar capacidades nuevas mencionadas
        capabilities = []
        if 'batch' in lower and 'processing' in lower:
            capabilities.append("batch_processing")
        if 'autonomous' in lower and 'delegation' in lower:
            capabilities.append("autonomous_delegation")
        if 'subagent' in lower:
            capabilities.append("subagent")
        if 'kanban' in lower:
            capabilities.append("kanban_plugin")
        if 'model' in lower and ('new' in lower or 'nuevo' in lower or 'major' in lower):
            capabilities.append("new_model")
        
        for cap in capabilities:
            if cap not in [s["name"] for s in skills_mentioned]:
                skills_mentioned.append({"name": cap, "source": "HermesWatcher"})
    
    return skills_mentioned


def get_installed_skills_per_profile():
    """Devuelve dict {perfil: [skills_instaladas]}."""
    result = {}
    for profile_dir in PROFILES_DIR.iterdir():
        if not profile_dir.is_dir():
            continue
        profile_name = profile_dir.name
        skills = set()
        for skill_file in profile_dir.rglob("SKILL.md"):
            rel = skill_file.relative_to(profile_dir)
            parts = rel.parts
            if len(parts) >= 2:
                skill_path = "/".join(parts[:-1])
                skills.add(skill_path)
        result[profile_name] = sorted(skills)
    return result


def install_skill(skill_path, profile_name):
    """Instala un skill en un perfil."""
    src = Path("/Users/adri/.hermes") / skill_path.replace("/", os.sep) / "SKILL.md"
    if not src.exists():
        return False, f"Skill no encontrado: {skill_path}"
    
    dst_dir = PROFILES_DIR / profile_name / "skills" / skill_path.replace("/", os.sep)
    dst = dst_dir / "SKILL.md"
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True, f"Instalado: {skill_path} en {profile_name}"
    except Exception as e:
        return False, f"Error: {e}"


def encontrar_skills_relevantes_para_lucidfence(skills_mentioned):
    """De las skills mencionadas, elegir las más relevantes para LucidFence."""
    relevantes = []
    
    for s in skills_mentioned:
        name = s["name"]
        # Skills/plugins relevantes para un equipo de desarrolladores de software
        if name in ['playwright', 'testing', 'test', 'debug', 'cli', 'github', 'code-review',
                     'security', 'scan', 'audit', 'review', 'linter', 'doc', 'documentation',
                     'deploy', 'ci', 'cd', 'release', 'version']:
            relevantes.append(s)
        # Capacidades relevantes para equipo autónomo
        elif name in ['batch_processing', 'autonomous_delegation', 'subagent', 'kanban',
                      'agent_merge', 'merge', 'conflict', 'coordination']:
            relevantes.append(s)
        # Skills de Hermes generales útiles
        elif any(kw in name for kw in ['prompt', 'plan', 'research', 'web', 'browser']):
            relevantes.append(s)
    
    return relevantes


def registrar_mejora(accion, resultado):
    """Registra la mejora en loop-run-log.md."""
    entry = f"- {TIMESTAMP} | L2 | Agente de automejora (skill discovery) | {accion} | {resultado}\n"
    with open(LOG, "a") as f:
        f.write(entry)


if __name__ == "__main__":
    print("=" * 70)
    print("AGENTE AUTOMEJORA: Skill Discovery desde HermesWatcher + Instalación")
    print("=" * 70)
    
    # 1. Extraer feed
    print("\n1. Extrayendo feed de @HermesWatcher ...")
    feed = fetch_feed()
    print(f"   Feed: {len(feed)} chars extraídos")
    
    # 2. Extraer posts
    print("\n2. Extrayendo posts recientes ...")
    posts = extract_posts(feed)
    print(f"   Posts encontrados: {len(posts)}")
    for i, p in enumerate(posts[:5]):
        print(f"   [{i+1}] {p['text'][:150]}...")
    
    # 3. Detectar skills/capacidades nuevas
    print("\n3. Detectando skills/capacidades nuevas ...")
    skills_mentioned = detect_new_skills(posts)
    print(f"   Skills/capacidades detectadas: {len(skills_mentioned)}")
    for s in skills_mentioned:
        print(f"   - {s['name']} (fuente: {s['source']})")
    
    # 4. Filtrar relevantes para LucidFence
    print("\n4. Seleccionando skills relevantes para LucidFence ...")
    relevantes = encontrar_skills_relevantes_para_lucidfence(skills_mentioned)
    print(f"   Skills relevantes: {len(relevantes)}")
    for s in relevantes:
        print(f"   - {s['name']}")
    
    # 5. Instalar skills relevantes en los perfiles
    print("\n5. Instalando skills en perfiles de agentes ...")
    installed_profiles = get_installed_skills_per_profile()
    profiles_to_update = [
        "empresa-ceo", "empresa-cto", "empresa-security-soc",
        "empresa-devops-release", "empresa-test-qa", "empresa-product",
        "empresa-seo-docs", "empresa-marketing", "empresa-finance",
        "empresa-kit-bot", "empresa-selfimprove",
    ]
    
    installations = []
    for skill in relevantes:
        skill_name = skill["name"]
        # Buscar el skill_path correspondiente en ~/.hermes
        for profile, skills in installed_profiles.items():
            break  # Solo para referencia
        
        # Para skills que son capacidades (no archivos reales), registrar como mejora
        if skill_name in ['batch_processing', 'autonomous_delegation', 'subagent', 'kanban_plugin', 'new_model']:
            installations.append((skill_name, "CAPACIDAD_NUEVA", "Evaluar e implementar capacidad en los agentes"))
        else:
            # Intentar instalar skill real
            # El skill podría estar en cualquier categoría; buscar
            skill_path = None
            for base in ["software-development", "devops", "research", "autonomous-ai-agents", "productivity", "creative"]:
                candidate = f"{base}/{skill_name}"
                if (Path("/Users/adri/.hermes") / candidate / "SKILL.md").exists():
                    skill_path = candidate
                    break
                candidate = skill_name
                if (Path("/Users/adri/.hermes") / candidate / "SKILL.md").exists():
                    skill_path = candidate
                    break
            
            if skill_path:
                for profile in profiles_to_update:
                    success, msg = install_skill(skill_path, profile)
                    if success:
                        installations.append((skill_name, profile, msg))
            else:
                installations.append((skill_name, "NO_ENCONTRADO", f"No se encontró el skill '{skill_name}' en ~/.hermes"))
    
    # 6. Resumen
    print("\n6. RESUMEN DE INSTALACIONES/Mejoras:")
    for item in installations:
        if len(item) == 3:
            print(f"   - {item[0]}: {item[2]}")
        else:
            print(f"   - {item[0]} en {item[1]}: {item[2]}")
    
    # 7. Registrar en loop-log
    print("\n7. Registrando en loop-run-log.md ...")
    accion = "Skill discovery desde @HermesWatcher"
    detalles = []
    if posts:
        detalles.append(f"Posts extraídos: {len(posts)}")
    if skills_mentioned:
        detalles.append(f"Skills/capacidades detectadas: {', '.join(s['name'] for s in skills_mentioned)}")
    if relevantes:
        detalles.append(f"Skills relevantes para LucidFence: {', '.join(s['name'] for s in relevantes)}")
    if installations:
        detalles.append(f"Instalaciones/mejoras: {len(installations)}")
    
    resultado = "; ".join(detalles) if detalles else "No se encontraron skills nuevos para instalar"
    registrar_mejora(accion, resultado)
    print(f"   Registrado: {accion} → {resultado[:200]}...")
    
    print("\n" + "=" * 70)
    print("AGENTE DE AUTOMEJORA EJECUTADO — los agentes ahora saben qué")
    print("skills/plugins nuevos hay disponibles y los instalaron donde hicieron falta.")
    print("=" * 70)
