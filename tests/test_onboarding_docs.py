"""Regression guards for the public onboarding claims tracked in #190/#191."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_english_entrypoint_does_not_publish_demo_credentials_or_invert_claim():
    english = (ROOT / "docs/README.en.md").read_text(encoding="utf-8")
    assert "demo1234" not in english
    assert "keep your data sovereignty" not in english
    assert "Fleet" in english


def test_root_readme_links_the_english_entrypoint():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "[English](docs/README.en.md)" in readme


def test_getting_started_is_the_first_user_document():
    index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    section = index.split("## Para el usuario y el cliente", 1)[1]
    first_document = next(
        line for line in section.splitlines() if line.startswith("| [`")
    )
    assert "GETTING_STARTED.md" in first_document
