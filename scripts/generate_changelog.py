#!/usr/bin/env python3
"""Generate a deterministic Keep-a-Changelog section from local git history."""
from __future__ import annotations

import argparse
import subprocess
from datetime import date
from pathlib import Path

HEADINGS = {"feat": "Added", "fix": "Fixed", "perf": "Changed", "refactor": "Changed",
            "docs": "Documentation", "test": "Testing", "ci": "CI", "build": "Build",
            "security": "Security"}


def collect(repo: Path, limit: int = 200) -> dict[str, list[str]]:
    result = subprocess.run(["git", "log", f"-{limit}", "--pretty=format:%s"], cwd=repo,
                            capture_output=True, text=True, timeout=20, check=True)
    groups: dict[str, list[str]] = {}
    seen = set()
    for subject in result.stdout.splitlines():
        clean = subject.strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        prefix = clean.split(":", 1)[0].split("(", 1)[0].lower()
        heading = HEADINGS.get(prefix, "Other")
        groups.setdefault(heading, []).append(clean)
    return groups


def render(groups: dict[str, list[str]], version: str = "Unreleased") -> str:
    lines = ["# Changelog", "", "All notable changes to LucidFence are documented here.", "",
             f"## [{version}] - {date.today().isoformat()}", ""]
    order = ["Security", "Added", "Fixed", "Changed", "Testing", "CI", "Build", "Documentation", "Other"]
    for heading in order:
        rows = groups.get(heading) or []
        if not rows:
            continue
        lines.extend([f"### {heading}", "", *[f"- {row}" for row in rows], ""])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--out", default="CHANGELOG.md")
    parser.add_argument("--version", default="Unreleased")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    output = Path(args.out)
    if not output.is_absolute():
        output = repo / output
    output.write_text(render(collect(repo), args.version), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
