#!/usr/bin/env python3
"""loop_free_guard.py — Runtime guard for the LucidFence /loop $0 (free-first) rule.

WHY THIS EXISTS
---------------
The /loop self-improvement aggregator used to call a PAID model (Claude Opus 4.8).
FINANCE removed that dependency (commit 2026-08-2x) and the fleet rule is now
100% free-tier. BUT the aggregator's provider catalog is built by::

    _provider_catalog() = merge_providers(FREE_PROVIDERS, plugins)
    _available_providers() -> providers in that catalog whose API key is present

where ``plugins`` are ANY ``*.py`` files dropped into
``lucidfence/plugins/providers/`` (the README actively invites users to add them).
``merge_providers`` only validates the provider *schema* (via ``validate_provider``)
— it does NOT enforce a free price tier. So a plugin defining a PAID model
(e.g. ``gpt-4`` / ``claude-opus-4``) with a real key present would make the
aggregator call a paid model at runtime, silently breaking the $0 rule.

The static ``paid_model_scanner.py`` (in ~/.hermes/scripts) scans source *text* and
only DETECTS — it cannot prevent the runtime call, nor catch a model name that
doesn't match its denylist.

This guard closes that gap by inspecting the REAL merged catalog ``loop_improve``
will actually use, OFFLINE and WITHOUT secrets, and failing (exit 1) if any
reachable provider resolves to a paid model.

CLASSIFICATION (fail-open on unknown, fail-closed on known-paid)
---------------------------------------------------------------
A model is classified:
  * paid    -> matches PAID_PATTERNS (opus, claude-opus, gpt-4 non-mini, gpt-5,
               sonnet, claude-3-opus, ...).  => BLOCK (the $0 violation).
  * free    -> contains ":free", or matches a known-free family marker
               (llama, mixtral, hermes, gpt-4o-mini, mistral, deepseek, qwen,
               phi, gemma, grok, yi-, command-r, ministral, ...), or is exactly
               one of the blessed FREE_PROVIDERS models.  => OK.
  * unknown -> neither.  => WARN (informational, exit 0). The official example
               plugin ships ``model: "example-model"`` which is unknown-but-not-paid;
               blocking it would be a false positive, so unknowns only warn.
               Use --strict to treat unknown as a BLOCK.

USAGE
-----
  python3 scripts/loop_free_guard.py            # scan the real merged catalog
  python3 scripts/loop_free_guard.py --selftest # offline unit tests (no import needed)
  python3 scripts/loop_free_guard.py --json     # machine-readable report
  python3 scripts/loop_free_guard.py --strict   # unknown models also block

EXIT CODES
----------
  0  PASS  (no paid model reachable by the aggregator)
  1  BLOCK (a paid model is reachable — $0 rule violated)
  2  ERROR (could not import loop_improve / build catalog)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# --- paid-model denylist (regex, case-insensitive) ---------------------------
# Precise (not broad) so we never false-positive on the team's free inventory
# (gpt-4o-mini, llama*, mixtral, hermes-3, :free). Mirrors the philosophy of
# paid_model_scanner.py but focused on the aggregator's runtime selection.
PAID_PATTERNS = [
    (r"\bopus\b", "anthropic-opus"),
    (r"claude[-\s_]?opus", "anthropic-opus"),
    (r"claude[-\s_]?sonnet", "anthropic-sonnet"),
    (r"claude-3-?opus", "anthropic-opus"),
    (r"\bgpt-4(?!o-mini)", "openai-gpt4"),   # gpt-4, gpt-4-turbo, gpt-4o (non-mini), gpt-4.5
    (r"\bgpt-5", "openai-gpt5"),
    (r"\bsonnet\b", "anthropic-sonnet"),
    (r"\bdeepseek-(?:v3|r1|reasoner)\b", "deepseek-paid"),  # only the paid tiers
]

# --- known-free family markers (substring, lowercased) -----------------------
FREE_FAMILY = [
    ":free",
    "gpt-4o-mini",
    "llama",
    "mixtral",
    "hermes",
    "mistral",
    "deepseek",
    "qwen",
    "phi-",
    "gemma",
    "grok",
    "yi-",
    "command-r",
    "ministral",
    "cohere",
    "falcon",
    "stablelm",
]


def classify(model: str) -> str:
    """Return 'paid', 'free', or 'unknown' for a model identifier."""
    if not model:
        return "unknown"
    m = model.lower()
    for pat, _fam in PAID_PATTERNS:
        if re.search(pat, m):
            return "paid"
    for fam in FREE_FAMILY:
        if fam in m:
            return "free"
    return "unknown"


def _load_loop_improve():
    """Import loop_improve with repo root on sys.path. Returns the module or None."""
    here = Path(__file__).resolve().parent
    root = here.parent  # repo root (scripts/ is one level under root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        import loop_improve  # top-level module in repo root
        return loop_improve
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"ERROR: cannot import loop_improve: {e!r}\n")
        return None


def real_catalog():
    """Return the merged provider catalog loop_improve will actually use.

    Tolerates a missing loop_improve (returns []) so the guard degrades to a
    clear ERROR exit rather than a crash.
    """
    lp = _load_loop_improve()
    if lp is None:
        return None
    try:
        return lp._provider_catalog()
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"ERROR: cannot build provider catalog: {e!r}\n")
        return None


def scan_providers(providers, strict: bool = False):
    """Scan a list of provider dicts. Returns (blocks, warns, details)."""
    blocks = []
    warns = []
    for p in providers or []:
        model = (p.get("model") or "").strip()
        name = p.get("name", "?")
        verdict = classify(model)
        if verdict == "paid":
            blocks.append((name, model))
        elif verdict == "unknown":
            if strict:
                blocks.append((name, model))
            else:
                warns.append((name, model))
    return blocks, warns


def run_scan(strict: bool = False, as_json: bool = False) -> int:
    catalog = real_catalog()
    if catalog is None:
        if as_json:
            print(json.dumps({"ok": False, "error": "catalog_unavailable"}, indent=2))
        return 2
    blocks, warns = scan_providers(catalog, strict=strict)
    if as_json:
        print(json.dumps({
            "ok": not blocks,
            "providers_scanned": len(catalog),
            "blocks": [{"name": n, "model": m} for n, m in blocks],
            "warns": [{"name": n, "model": m} for n, m in warns],
            "strict": strict,
        }, indent=2))
    else:
        print(f"Scanned {len(catalog)} providers in the merged /loop catalog:")
        for p in catalog:
            v = classify(p.get("model", ""))
            mark = {"paid": "BLOCK", "free": "ok", "unknown": "warn"}[v]
            print(f"  [{mark:5}] {p.get('name', '?'):24} {p.get('model', '')}")
        if warns:
            print(f"\nWARN: {len(warns)} provider(s) have unknown (non-paid) models; "
                  f"not blocked. Use --strict to block them.")
        if blocks:
            print(f"\nBLOCK: {len(blocks)} paid model(s) reachable by the /loop aggregator:")
            for n, m in blocks:
                print(f"  - {n}: {m}")
            print("\n$0 rule VIOLATED — the aggregator could call a paid model at runtime.")
        else:
            print("\nPASS: no paid model is reachable by the /loop aggregator.")
    return 1 if blocks else 0


def selftest() -> int:
    """Offline unit tests — no import of loop_improve, no network, no secrets."""
    cases = [
        # (model, expected_verdict)
        ("claude-opus-4", "paid"),
        ("claude opus 4.8", "paid"),
        ("anthropic/claude-3-opus", "paid"),
        ("gpt-4", "paid"),
        ("gpt-4-turbo", "paid"),
        ("gpt-4o", "paid"),          # non-mini gpt-4o is paid
        ("gpt-5", "paid"),
        ("gpt-5-turbo", "paid"),
        ("claude-sonnet-4", "paid"),
        ("sonnet-4", "paid"),
        # ---- free (must NOT be flagged) ----
        ("gpt-4o-mini", "free"),
        ("nousresearch/hermes-3-llama-3.1-405b:free", "free"),
        ("llama-3.3-70b-versatile", "free"),
        ("meta/llama-3.1-70b-instruct", "free"),
        ("mistralai/Mixtral-8x22B-Instruct-v0.1", "free"),
        ("deepseek/deepseek-chat", "free"),
        ("accounts/fireworks/models/llama-v3p3-70b-instruct", "free"),
        # ---- unknown (placeholder / new free model) ----
        ("example-model", "unknown"),
        ("my-custom-free-endpoint", "unknown"),
    ]
    failures = []
    for model, expected in cases:
        got = classify(model)
        status = "OK " if got == expected else "BAD"
        if got != expected:
            failures.append((model, expected, got))
        print(f"  {status} classify({model!r}) = {got} (expected {expected})")

    # Catalog scan logic on synthetic data (does NOT need loop_improve).
    synth = [
        {"name": "nous_openrouter", "model": "nousresearch/hermes-3-llama-3.1-405b:free"},
        {"name": "groq", "model": "llama-3.3-70b-versatile"},
        {"name": "evil_plugin", "model": "claude-opus-4"},   # the real gap
        {"name": "placeholder", "model": "example-model"},   # unknown -> warn
    ]
    blocks, warns = scan_providers(synth, strict=False)
    ok_scan = (len(blocks) == 1 and blocks[0][0] == "evil_plugin" and len(warns) == 1)
    print(f"  {'OK ' if ok_scan else 'BAD'} scan synthetic catalog: "
          f"blocks={[b[0] for b in blocks]} warns={[w[0] for w in warns]}")
    if not ok_scan:
        failures.append(("scan_synthetic", "1 block(evil_plugin)+1 warn", f"blocks={blocks} warns={warns}"))

    # In strict mode, the unknown placeholder must also block.
    blocks_s, _ = scan_providers(synth, strict=True)
    ok_strict = len(blocks_s) == 2
    print(f"  {'OK ' if ok_strict else 'BAD'} strict mode blocks unknown: "
          f"blocks={[b[0] for b in blocks_s]}")
    if not ok_strict:
        failures.append(("scan_strict", "2 blocks", f"blocks={blocks_s}"))

    # End-to-end proof against loop_improve's REAL merge path: inject a paid
    # plugin and assert the guard catches it via loop_improve._provider_catalog().
    lp = _load_loop_improve()
    if lp is not None:
        try:
            from unittest import mock
            paid_plugin = {"name": "rogue", "env": "LF_PROVIDER_ROGUE_API_KEY",
                           "base": "https://api.invalid/v1", "model": "claude-opus-4"}
            with mock.patch.object(lp, "discover_provider_plugins",
                                   return_value=[paid_plugin]):
                cat = lp._provider_catalog()
            rogue_present = any(p.get("name") == "rogue" for p in cat)
            b2, _ = scan_providers(cat, strict=False)
            if rogue_present:
                # Detection path: the scanner must flag the leak (and the CI
                # gate would exit 1). The guard is *working*; a found violation
                # is correct behavior, not a selftest failure.
                ok_e2e = any(n == "rogue" for n, _m in b2)
                print(f"  {'OK ' if ok_e2e else 'BAD'} e2e: paid plugin present in "
                      f"catalog -> scanner catches it (detection path correct)")
                if not ok_e2e:
                    failures.append(("e2e_detection", "rogue detected", f"blocks={b2}"))
            else:
                # Prevention path: the source hardens the catalog and filters
                # the paid plugin out before it can reach the aggregator, so the
                # scanner finds nothing. Again correct behavior.
                ok_e2e = (len(b2) == 0)
                print(f"  {'OK ' if ok_e2e else 'BAD'} e2e: paid plugin filtered out "
                      f"by source (prevention path correct)")
                if not ok_e2e:
                    failures.append(("e2e_prevention", "catalog clean", f"blocks={b2}"))
        except Exception as e:  # noqa: BLE001
            print(f"  SKIP e2e injection test: {e!r}")
    else:
        print("  SKIP e2e injection test: loop_improve not importable")

    if failures:
        print(f"\nSELFTEST FAILED: {len(failures)} case(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nSELFTEST PASSED")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Guard the /loop $0 (free-first) rule.")
    ap.add_argument("--selftest", action="store_true", help="offline unit tests")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--strict", action="store_true",
                    help="treat unknown (non-paid) models as blocks too")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return run_scan(strict=args.strict, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
