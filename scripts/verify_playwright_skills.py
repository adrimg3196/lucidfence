#!/usr/bin/env python3
"""
Verify that playwright-cli and playwright-component-testing skills
created in this session are installed in all key profiles.

Usage: python3 scripts/verify_playwright_skills.py
"""

import os
from pathlib import Path

PROFILES_DIR = Path("/Users/adri/.hermes/profiles")
SKILLS_TO_CHECK = ["playwright-cli", "playwright-component-testing"]
KEY_PROFILES = [
    "empresa-test-qa",
    "empresa-cto",
    "empresa-devops-release",
    "empresa-product",
    "empresa-seo-docs",
    "empresa-security-soc",
]


def check_skill_installed(profile: str, skill: str) -> tuple[bool, str]:
    """Check if a skill is installed in a profile.

    Returns (installed, location) where location is empty if not installed.
    """
    profile_dir = PROFILES_DIR / profile / "skills"
    if not profile_dir.exists():
        return False, "profile dir missing"

    # Search for the skill anywhere in the profile's skills tree
    for skill_file in profile_dir.rglob("SKILL.md"):
        # Get relative path from profile_dir/skills
        rel = skill_file.relative_to(profile_dir)
        parts = rel.parts
        if len(parts) >= 2:
            rel_path = "/".join(parts[:-1])
        else:
            rel_path = rel.stem

        if skill in rel_path:
            return True, str(rel_path)

    return False, "not found"


def main():
    print("=" * 60)
    print("Verificación de skills playwright en perfiles clave")
    print("=" * 60)

    all_ok = True
    for profile in KEY_PROFILES:
        print(f"\n--- {profile} ---")
        for skill in SKILLS_TO_CHECK:
            installed, location = check_skill_installed(profile, skill)
            if installed:
                print(f"  ✓ {skill}: instalado en {location}")
            else:
                print(f"  ✗ {skill}: NO INSTALADO ({location})")
                all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("RESULTADO: Todos los skills instalados correctamente ✓")
    else:
        print("RESULTADO: Faltan skills por instalar ✗")
    print("=" * 60)

    return 0 if all_ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
