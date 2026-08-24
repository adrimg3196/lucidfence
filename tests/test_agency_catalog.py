"""Behavioral tests for the pinned Agency Agents trust root."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from scripts import generate_agency_catalog as catalog


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _documents():
    with open(os.path.join(ROOT, "config", "agency-agents.lock.json"), encoding="utf-8") as fh:
        lock = json.load(fh)
    with open(os.path.join(ROOT, "data", "agency_catalog.json"), encoding="utf-8") as fh:
        inventory = json.load(fh)
    return lock, inventory


def _verify_mutation(mutator):
    lock, inventory = _documents()
    lock = copy.deepcopy(lock)
    inventory = copy.deepcopy(inventory)
    mutator(lock, inventory)
    with tempfile.TemporaryDirectory(prefix="agency-catalog-test-") as tmp:
        os.makedirs(os.path.join(tmp, "config"))
        os.makedirs(os.path.join(tmp, "data"))
        with open(os.path.join(tmp, "config", "agency-agents.lock.json"), "wb") as fh:
            fh.write(catalog.canonical_document(lock))
        with open(os.path.join(tmp, "data", "agency_catalog.json"), "wb") as fh:
            fh.write(catalog.canonical_document(inventory))
        return catalog.verify_repository(tmp)


def test_agency_catalog_is_complete_and_pinned():
    errors = catalog.verify_repository(ROOT)
    assert errors == [], errors
    lock, inventory = _documents()
    assert lock["source"]["repository"] == "msitarzewski/agency-agents"
    assert lock["source"]["commit"] == "ebe9c99acb5c96f9468de368d8bead775387d1a7"
    assert lock["source"]["license"] == "MIT"
    assert lock["profile_count"] == len(lock["profiles"]) == 270
    assert lock["division_count"] == len(lock["divisions"]) == 17
    assert inventory["schema"] == "lucidfence-agency-catalog/v1"
    assert inventory["lock"] == lock


def test_agency_catalog_serialization_is_deterministic():
    lock, inventory = _documents()
    assert catalog.canonical_document(lock) == catalog.canonical_document(copy.deepcopy(lock))
    assert catalog.canonical_document(inventory) == catalog.canonical_document(copy.deepcopy(inventory))


def test_agency_catalog_rejects_pin_license_count_division_path_or_hash_drift():
    mutations = [
        lambda lock, _catalog: lock["source"].__setitem__("commit", "0" * 40),
        lambda lock, _catalog: lock["source"].__setitem__("license", "Apache-2.0"),
        lambda lock, _catalog: lock.__setitem__("profile_count", 269),
        lambda lock, _catalog: lock["divisions"].pop(),
        lambda lock, _catalog: lock["profiles"][0].__setitem__("path", "academic/renamed.md"),
        lambda lock, _catalog: lock["profiles"][0].__setitem__("sha256", "0" * 64),
    ]
    for mutate in mutations:
        errors = _verify_mutation(mutate)
        assert errors, f"mutation was accepted: {mutate}"


def test_agency_catalog_rejects_embedded_lock_mismatch():
    errors = _verify_mutation(
        lambda _lock, inventory: inventory["lock"]["source"].__setitem__("commit", "0" * 40)
    )
    assert any("embedded lock" in error for error in errors), errors


def test_agency_catalog_rejects_catalog_profile_drift():
    errors = _verify_mutation(
        lambda _lock, inventory: inventory["profiles"][0].__setitem__("sha256", "f" * 64)
    )
    assert errors


def test_agency_catalog_rejects_coordinated_inventory_rewrite_without_source():
    def rewrite(lock, inventory):
        lock["profiles"][0]["sha256"] = "0" * 64
        lock["inventory_sha256"] = catalog.sha256_bytes(catalog.canonical_bytes(lock["profiles"]))
        inventory["lock"] = copy.deepcopy(lock)
        inventory["profiles"] = copy.deepcopy(lock["profiles"])

    errors = _verify_mutation(rewrite)
    assert any("fixed inventory" in error for error in errors), errors


def test_source_generation_rejects_a_dirty_checkout():
    with tempfile.TemporaryDirectory(prefix="agency-source-cleanliness-") as tmp:
        source = Path(tmp)
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        subprocess.run(
            ["git", "-C", str(source), "config", "user.name", "Catalog Test"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "config", "user.email", "catalog@example.invalid"],
            check=True,
        )
        tracked = source / "tracked.txt"
        tracked.write_text("fixed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(source), "add", "tracked.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(source), "commit", "-q", "-m", "fixture"],
            check=True,
        )
        catalog._require_clean_checkout(source)

        tracked.write_text("changed\n", encoding="utf-8")
        try:
            catalog._require_clean_checkout(source)
        except ValueError as exc:
            assert "clean" in str(exc)
        else:
            raise AssertionError("dirty source checkout was accepted")
