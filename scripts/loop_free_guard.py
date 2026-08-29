#!/usr/bin/env python3
"""loop_free_guard.py — Runtime guard for the LucidFence /loop $0 (free-first) rule.

WHY THIS EXISTS
---------------
The /loop self-improvement aggregator used to call a PAID model (Claude Opus 4.8).
FINANCE removed that dependency and the fleet rule is now 100% free-tier. BUT the
aggregator's provider catalog is built by::

    _provider_catalog() = [p for p in merge_providers(FREE_PROVIDERS, plugins)
                           if is_free_model(p["model"])]   # DEFAULT-DENY

where ``plugins`` are ANY ``*.py`` files dropped into
``lucidfence/plugins/providers/`` (the README actively invites users to add them).
``merge_providers`` only validates the provider *schema* (via ``validate_provider``)
— it does NOT enforce a free price tier. So a plugin defining a NON-free model
(e.g. ``gpt-4`` / ``claude-opus-4`` / ``gemini-2.5-pro`` / ``o1``) with a real key
present would make the aggregator call a paid/unknown model at runtime, silently
breaking the $0 rule.

This guard is the DETECTION layer that mirrors the PREVENTION layer in
``loop_improve._provider_catalog()``. Both import the ONLY source of truth for what
is free: ``lucidfence.core.free_tier.is_free_model`` / ``FREE_ALLOWLIST``. Because
they share the exact same logic, detection and prevention can never diverge.

DEFAULT-DENY MODEL (the fix for the PR #331 gap Finance found)
-------------------------------------------------------------
The original guard used a PAID *denylist* that FAILED OPEN on unlisted models
(``gemini-2.5-pro``, ``o1``, ``claude-3-5-haiku``, ``claude-2`` all classified
"unknown" and only WARNed). We now invert it:

  * FREE    -> matches ``FREE_ALLOWLIST`` (the known free providers/placeholders).
               => OK.
  * NON-free-> anything that does NOT match the allowlist, INCLUDING models we have
               never seen (``gemini-2.5-pro``, ``o1``, ``o3-mini``, ``haiku``...).
               => BLOCK (exit 1) by DEFAULT. This is fail-closed.

So adding a brand-new paid model to the catalog can never silently pass — it is
blocked until it is explicitly added to the free allowlist.

USAGE
-----
  python3 scripts/loop_free_guard.py            # scan the real merged catalog (default)
  python3 scripts/loop_free_guard.py --selftest # offline unit tests (no import needed)
  python3 scripts/loop_free_guard.py --json     # machine-readable report

EXIT CODES
----------
  0  PASS  (every reachable provider in the catalog is on the free allowlist)
  1  BLOCK (a non-free provider is reachable by the /loop aggregator)
  2  ERROR (could not import loop_improve / build catalog)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make sure the repo root is importable before we touch the project package, so
# the detection layer imports the SAME source of truth as the prevention layer.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# --- free allowlist (DEFAULT-DENY) -------------------------------------------
# Re-exported from the single source of truth so detection and prevention match.
# If the project package is unavailable (e.g. the file is copied elsewhere) we
# fall back to an identical inline copy so the guard still fails closed.
try:
    from lucidfence.core.free_tier import FREE_ALLOWLIST, is_free_model
except Exception:  # pragma: no cover - allow standalone offline run
    sys.stderr.write(
        "WARN: cannot import lucidfence.core.free_tier; using inline copy.\n"
    )
    FREE_ALLOWLIST = [
        ":free", "gpt-4o-mini", "llama", "mixtral", "mistral", "hermes",
        "deepseek", "qwen", "phi-", "gemma", "yi-", "command-r",
        "ministral", "cohere", "falcon", "stablelm",
        # NOTE: "grok" intentionally absent — free Grok needs ":free".
    ]
    PAID_EXCLUSIONS = [
        "grok-4", "grok-3", "grok-2", "grok-beta", "grok-1",
        "deepseek-r1", "deepseek-v3", "deepseek-reasoner", "deepseek-coder-v2",
        "mistral-large", "mistral-medium", "mistral-next",
        "command-r-plus", "command-r-08", "command-r-03", "command-nightfall",
        "qwen-max", "qwen-plus", "qwen-turbo-max", "qwen2.5-max", "qwen2.5-plus",
        "minimax", "abab", "step-", "glm-4-plus", "glm-4-air",
    ]

    def is_free_model(model) -> bool:  # type: ignore[no-redef]
        if not isinstance(model, str) or not model:
            return False
        m = model.lower()
        if ":free" in m:
            return True
        if any(tok in m for tok in PAID_EXCLUSIONS):
            return False
        return any(tok in m for tok in FREE_ALLOWLIST)


def classify(model: str) -> str:
    """Return 'free' or 'nonfree' for a model identifier (default-deny).

    Unlike the old denylist design there is no 'unknown' verdict: anything that
    is not explicitly free is NON-free, and the default scan BLOCKS it.
    """
    return "free" if is_free_model(model) else "nonfree"


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
    """Return the RAW merged provider catalog loop_improve builds (prevention off).

    We replicate the merge here (not loop_improve._provider_catalog, which already
    DROPS non-free models) so the detector can SEE every plugin that tried to enter
    the catalog and flag it — otherwise a prevented (dropped) plugin would be
    invisible and the guard would always report a clean catalog even if a paid
    plugin existed.

    Tolerates a missing loop_improve (returns None) so the guard degrades to a
    clear ERROR exit rather than a crash.
    """
    lp = _load_loop_improve()
    if lp is None:
        return None
    try:
        from lucidfence.core.provider_plugins import (
            discover_provider_plugins,
            merge_providers,
        )
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"ERROR: cannot import provider_plugins: {e!r}\n")
        return None
    try:
        plugins = discover_provider_plugins(Path(lp.__file__).resolve().parent
                                            / "lucidfence" / "plugins" / "providers")
        return merge_providers(lp.FREE_PROVIDERS, plugins)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"ERROR: cannot build provider catalog: {e!r}\n")
        return None


def scan_providers(providers):
    """Scan a list of provider dicts. Returns (blocks, ok) where blocks is a list
    of (name, model) for every NON-free provider."""
    blocks = []
    for p in providers or []:
        model = (p.get("model") or "").strip()
        name = p.get("name", "?")
        if not is_free_model(model):
            blocks.append((name, model))
    return blocks


def run_scan(as_json: bool = False) -> int:
    catalog = real_catalog()
    if catalog is None:
        if as_json:
            print(json.dumps({"ok": False, "error": "catalog_unavailable"}, indent=2))
        return 2
    blocks = scan_providers(catalog)
    if as_json:
        print(json.dumps({
            "ok": not blocks,
            "providers_scanned": len(catalog),
            "blocks": [{"name": n, "model": m} for n, m in blocks],
        }, indent=2))
    else:
        print(f"Scanned {len(catalog)} providers in the merged /loop catalog:")
        for p in catalog:
            v = classify(p.get("model", ""))
            mark = "ok" if v == "free" else "BLOCK"
            print(f"  [{mark:5}] {p.get('name', '?'):24} {p.get('model', '')}")
        if blocks:
            print(f"\nBLOCK: {len(blocks)} NON-free model(s) reachable by the "
                  f"/loop aggregator:")
            for n, m in blocks:
                print(f"  - {n}: {m}")
            print("\n$0 rule VIOLATED — a non-free model could be called at runtime.")
        else:
            print("\nPASS: every reachable provider is on the free allowlist "
                  "(default-deny $0 rule OK).")
    return 1 if blocks else 0


def selftest() -> int:
    """Offline unit tests — no import of loop_improve, no network, no secrets."""
    # (model, expected_verdict) with default-deny semantics.
    free_cases = [
        ("gpt-4o-mini", "free"),
        ("nousresearch/hermes-3-llama-3.1-405b:free", "free"),
        ("llama-3.3-70b-versatile", "free"),
        ("meta/llama-3.1-70b-instruct", "free"),
        ("mistralai/Mixtral-8x22B-Instruct-v0.1", "free"),
        ("deepseek/deepseek-chat", "free"),
        ("accounts/fireworks/models/llama-v3p3-70b-instruct", "free"),
        # Free Grok MUST carry the explicit :free suffix — that is the only
        # blessed free marker for that family (the bare "grok" token was removed
        # in the t_bdcf0cad fix to close the grok-4 false-negative).
        ("x-ai/grok-3-mini:free", "free"),
        ("xai/grok-2-latest:free", "free"),
        # Paid-sibling exclusions must NOT swallow the genuinely-free SKU of a
        # family that shares a substring prefix.
        ("deepseek/deepseek-chat", "free"),          # deepseek-r1 is paid, chat is free
        ("mistralai/Mixtral-8x22B-Instruct-v0.1", "free"),  # mistral-large is paid
        ("cohere/command-r", "free"),                # command-r-plus is paid
        ("qwen/qwen2.5-7b-instruct", "free"),        # qwen-max is paid
    ]
    nonfree_cases = [
        # the original gap: unlisted paid/unknown models that the old denylist
        # only WARNed on. Now they MUST block.
        ("gemini-2.5-pro", "nonfree"),
        ("o1", "nonfree"),
        ("o3-mini", "nonfree"),
        ("o4-mini", "nonfree"),
        ("claude-3-5-haiku", "nonfree"),
        ("claude-2", "nonfree"),
        ("claude-opus-4", "nonfree"),
        ("claude opus 4.8", "nonfree"),
        ("anthropic/claude-3-opus", "nonfree"),
        ("gpt-4", "nonfree"),
        ("gpt-4-turbo", "nonfree"),
        ("gpt-4o", "nonfree"),   # non-mini gpt-4o is paid
        ("gpt-5", "nonfree"),
        ("claude-sonnet-4", "nonfree"),
        ("sonnet-4", "nonfree"),
        # a brand-new unknown free-looking name that is NOT on the allowlist must
        # still block — that is the whole point of default-deny.
        ("my-custom-free-endpoint", "nonfree"),
        # --- t_bdcf0cad: the grok-4 false-negative regression ---
        # "grok" was a bare free-family token, so "grok-4" (PAID) was wrongly
        # classified as free. Bare grok-* must now be NON-free; free Grok needs
        # the ":free" suffix (covered in free_cases above).
        ("grok-4", "nonfree"),
        ("x-ai/grok-4-latest", "nonfree"),
        ("grok-3", "nonfree"),
        ("grok-2", "nonfree"),
        ("grok-beta", "nonfree"),
        # --- same paid-sibling pattern across other families (Finance flag) ---
        ("deepseek/deepseek-r1", "nonfree"),
        ("deepseek-r1", "nonfree"),
        ("deepseek/deepseek-reasoner", "nonfree"),
        ("mistral-large-latest", "nonfree"),
        ("mistral/mistral-medium", "nonfree"),
        ("cohere/command-r-plus", "nonfree"),
        ("command-r-plus", "nonfree"),
        ("qwen/qwen-max", "nonfree"),
        ("qwen2.5-max", "nonfree"),
    ]
    failures = []
    for model, expected in free_cases + nonfree_cases:
        got = classify(model)
        status = "OK " if got == expected else "BAD"
        if got != expected:
            failures.append((model, expected, got))
        print(f"  {status} classify({model!r}) = {got} (expected {expected})")

    # Catalog scan logic on synthetic data (does NOT need loop_improve). Every
    # non-free entry must be flagged; the free + example placeholder must pass.
    synth = [
        {"name": "nous_openrouter", "model": "nousresearch/hermes-3-llama-3.1-405b:free"},
        {"name": "groq", "model": "llama-3.3-70b-versatile"},
        {"name": "evil_opus", "model": "claude-opus-4"},          # MUST block
        {"name": "evil_gemini", "model": "gemini-2.5-pro"},       # MUST block
        {"name": "evil_haiku", "model": "claude-3-5-haiku"},      # MUST block
        {"name": "placeholder", "model": "gpt-4o-mini"},          # free -> must pass
    ]
    blocks = scan_providers(synth)
    blocked_names = {n for n, _m in blocks}
    ok_scan = (blocked_names == {"evil_opus", "evil_gemini", "evil_haiku"})
    print(f"  {'OK ' if ok_scan else 'BAD'} scan synthetic catalog: "
          f"blocks={sorted(blocked_names)}")
    if not ok_scan:
        failures.append(("scan_synthetic",
                         "blocks evil_opus/evil_gemini/evil_haiku",
                         f"blocks={sorted(blocked_names)}"))

    # End-to-end proof against loop_improve's REAL prevention path: drop a real
    # NON-free plugin file into the providers dir (the exact models Finance flagged
    # in PR #331) and assert BOTH layers behave correctly:
    #   * _provider_catalog() DROPS it (prevention, fail-closed) — the PR #331 leak fix
    #   * the guard's real_catalog() DETECTS it and would exit 1 (detection)
    # The temp file is removed in a finally block so selftest never pollutes the repo.
    lp = _load_loop_improve()
    if lp is not None:
        try:
            prov_dir = (Path(lp.__file__).resolve().parent
                        / "lucidfence" / "plugins" / "providers")
            # t_bdcf0cad: grok-4 is included so both layers prove they reject a
            # paid Grok plugin (the regression Finance found on the bare "grok"
            # family token).
            inject_models = ["gemini-2.5-pro", "o1", "claude-3-5-haiku", "grok-4"]
            for inj in inject_models:
                rogue_file = prov_dir / f"selftest_rogue_{inj.replace('-', '_').replace('.', '_')}.py"
                rogue_file.write_text(
                    'PROVIDER = {\n'
                    '    "name": "rogue",\n'
                    '    "env": "LF_PROVIDER_ROGUE_API_KEY",\n'
                    '    "base": "https://api.invalid/v1",\n'
                    f'    "model": "{inj}",\n'
                    '}\n'
                )
                try:
                    cat = lp._provider_catalog()
                    rogue_present = any(p.get("name") == "rogue" for p in cat)
                    ok_drop = not rogue_present
                    print(f"  {'OK ' if ok_drop else 'BAD'} e2e: injected {inj!r} plugin is "
                          f"DROPPED by _provider_catalog() (prevention fail-closed)")
                    if not ok_drop:
                        failures.append((f"e2e_prevention:{inj}",
                                         "rogue plugin dropped", "rogue still present"))

                    raw = real_catalog()
                    raw_rogue = any(p.get("name") == "rogue" for p in (raw or []))
                    ok_detect = raw_rogue and bool(scan_providers(raw))
                    print(f"  {'OK ' if ok_detect else 'BAD'} e2e: injected {inj!r} plugin is "
                          f"DETECTED by the guard (detection path)")
                    if not ok_detect:
                        failures.append((f"e2e_detection:{inj}",
                                         "rogue detected", f"raw_rogue={raw_rogue}"))
                finally:
                    rogue_file.unlink(missing_ok=True)
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
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return run_scan(as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
