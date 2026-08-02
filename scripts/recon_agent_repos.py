#!/usr/bin/env python3
"""Recon de repos GitHub que MEJORAN a este agente (Hermes):
frameworks de agentes, skills, planning, tool-use, memory, multi-agent.
Devuelve minimo 3 referencias clasificadas por angulo de mejora.

Con --apply: si aparecen repos NUEVOS no referenciados en la skill
agent-upgrade, los anade a la skill + docs y hace commit+push al repo
de LucidFence. Asi el agente se mejora solo cada dia (impacto real).

GitHub API publica (sin auth, rate limit 60/h)."""
import json, urllib.request, urllib.parse, sys, os, subprocess

QUERIES = [
    "ai agent framework",
    "agentic workflow tool use",
    "llm agent memory",
    "mcp server",
    "multi-agent orchestration",
    "agent skills framework",
    "agent planning verify",
]
ANGLES = {
    "skills": ["skill", "superpower", "prompt"],
    "planning": ["plan", "planner", "task decomposition", "todo"],
    "tooluse": ["tool use", "tool-use", "function calling", "mcp"],
    "memory": ["memory", "rag", "context", "recall"],
    "multiagent": ["multi-agent", "multiagent", "orchestrat", "delegate", "crew"],
}

def classify(desc, name):
    t = (desc + " " + name).lower()
    for a, kws in ANGLES.items():
        if any(k in t for k in kws):
            return a
    return "other"

PATTERN = {
    "skills": "skill TDD + verification-before-completion (superpowers)",
    "planning": "DAG plan-execute + checkpoint (xagent)",
    "tooluse": "tool auto-discovery + MCP/A2A (langchain/autogen/MAF)",
    "memory": "memory vectorial + RAG (xagent/langchain)",
    "multiagent": "role-play SOP + nested agents (MetaGPT/xagent)",
    "other": "revisar manualmente",
}

SKILL_PATH = "/Users/adri/.hermes/skills/operations/agent-upgrade/SKILL.md"
DOCS_PATH = "/Users/adri/geofence-uem/docs/agent-upgrade/SKILL.md"
REPO = "/Users/adri/geofence-uem"

def recon():
    seen = set()
    repos = []
    for q in QUERIES:
        url = "https://api.github.com/search/repositories?q=" + urllib.parse.quote(q) + "&sort=stars&order=desc&per_page=4"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "hermes-agent-recon"})
            d = json.load(urllib.request.urlopen(req, timeout=15))
        except Exception:
            continue
        for r in d.get("items", []):
            f = r["full_name"]
            if f in seen:
                continue
            seen.add(f)
            repos.append((f, r["stargazers_count"], r.get("description") or "", r["html_url"], r.get("language") or "", classify(r.get("description") or "", f)))
        if len(repos) >= 8:
            break
    return repos

def current_refs():
    """Repos ya referenciados en la skill (formato '- owner/repo (...)')."""
    try:
        with open(SKILL_PATH) as fh:
            txt = fh.read()
    except FileNotFoundError:
        return set()
    import re
    return set(re.findall(r"-\s*([\w.\-]+/[\w.\-]+)\s*\(", txt))

def apply_updates(repos):
    known = current_refs()
    new = [(n, s, d, u, l, a) for (n, s, d, u, l, a) in repos if n not in known]
    if not new:
        print("Sin repos nuevos respecto a la skill. Skill ya al dia.")
        return False
    print(f"Repos NUEVOS a integrar: {len(new)}")
    for n, s, d, u, l, a in new:
        print(f"  + {n} ★{s} #{a} -> {PATTERN.get(a,'revisar')}")
    # anade a la skill (seccion Referencias)
    with open(SKILL_PATH) as fh:
        skill = fh.read()
    block = "\n".join(f"- {n} ({PATTERN.get(a,'revisar manualmente')})" for (n, s, d, u, l, a) in new)
    if "## Referencias" in skill:
        skill = skill.replace("## Referencias (repos de recon)", "## Referencias (repos de recon)\n" + block + "\n")
    else:
        skill += "\n## Referencias (repos de recon)\n" + block + "\n"
    with open(SKILL_PATH, "w") as fh:
        fh.write(skill)
    # specular al docs del repo
    try:
        with open(DOCS_PATH) as fh:
            docs = fh.read()
        if "## Referencias" in docs:
            docs = docs.replace("## Referencias (repos de recon)", "## Referencias (repos de recon)\n" + block + "\n")
        else:
            docs += "\n## Referencias (repos de recon)\n" + block + "\n"
        with open(DOCS_PATH, "w") as fh:
            fh.write(docs)
    except FileNotFoundError:
        pass
    # commit + push en el repo (docs)
    try:
        subprocess.run(["git", "-C", REPO, "add", "docs/agent-upgrade/SKILL.md"], check=True)
        subprocess.run(["git", "-C", REPO, "commit", "-m",
                        "chore(agent): auto-integracion de repos nuevos desde recon diario\n\n" +
                        "\n".join(f"- {n} ({PATTERN.get(a,'?')})" for (n,s,d,u,l,a) in new)],
                       check=True,
                       env={**os.environ, "GIT_AUTHOR_NAME": "Hermes Agent", "GIT_AUTHOR_EMAIL": "hermes@local",
                            "GIT_COMMITTER_NAME": "Hermes Agent", "GIT_COMMITTER_EMAIL": "hermes@local"})
        subprocess.run(["git", "-C", REPO, "push", "origin", "HEAD:main"], check=True)
        print("Skill actualizada y pusheada a main.")
    except subprocess.CalledProcessError as e:
        print(f"WARN: no se pudo commitear/pushear: {e}")
    return True

def main():
    apply = "--apply" in sys.argv
    repos = recon()
    print("=== RECON AGENT REPOS — mejora para Hermes ===\n")
    for i, (n, s, desc, u, l, ang) in enumerate(repos[:8], 1):
        print(f"{i}. {n}  ★{s}  [{l}] #{ang}")
        print(f"   {desc}")
        print(f"   patch: {PATTERN.get(ang, 'revisar manualmente')}")
        print(f"   {u}\n")
    print(f"Total referencias: {len(repos)} (minimo 3)")
    if apply:
        print("\n--- modo --apply ---")
        apply_updates(repos)

if __name__ == "__main__":
    main()
