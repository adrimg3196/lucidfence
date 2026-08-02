#!/usr/bin/env python3
"""Recon de repos GitHub que MEJORAN a este agente (Hermes):
frameworks de agentes, skills, planning, tool-use, memory, multi-agent.
Devuelve minimo 3 referencias clasificadas por angulo de mejora.
GitHub API publica (sin auth, rate limit 60/h)."""
import json, urllib.request, urllib.parse, sys

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

# que patron de mejora aplica cada angulo (usa skill agent-upgrade)
PATTERN = {
    "skills": "skill TDD + verification-before-completion (superpowers)",
    "planning": "DAG plan-execute + checkpoint (xagent)",
    "tooluse": "tool auto-discovery + MCP/A2A (langchain/autogen/MAF)",
    "memory": "memory vectorial + RAG (xagent/langchain)",
    "multiagent": "role-play SOP + nested agents (MetaGPT/xagent)",
    "other": "revisar manualmente",
}

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

print("=== RECON AGENT REPOS — mejora para Hermes ===\n")
for i, (n, s, desc, u, l, ang) in enumerate(repos[:8], 1):
    print(f"{i}. {n}  ★{s}  [{l}] #{ang}")
    print(f"   {desc}")
    print(f"   patch: {PATTERN.get(ang, 'revisar manualmente')}")
    print(f"   {u}\n")
print(f"Total referencias: {len(repos)} (minimo 3)")
