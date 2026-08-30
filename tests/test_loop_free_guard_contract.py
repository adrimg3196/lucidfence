from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Import the real guard from scripts/ as a standalone module (it can run
# offline without the project package, so we do not require lucidfence importable).
ROOT = Path(__file__).resolve().parent.parent
GUARD_PATH = ROOT / "scripts" / "loop_free_guard.py"

_spec = importlib.util.spec_from_file_location("loop_free_guard", str(GUARD_PATH))
loop_free_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(loop_free_guard)
classify = loop_free_guard.classify


def test_default_deny_blocks_known_paid_grok4():
    """t_bdcf0cad regression: bare 'grok' family must NOT be blessed free.

    The fail-open branch version (finance/loop-free-aggregator, 672d0f8)
    classified 'grok-4' as 'free' and 'gemini-2.5-pro' as 'unknown' (WARN,
    exit 0) — silently reopening the $0 durability gap. The contract is
    fail-closed: any non-allowlisted model is nonfree and BLOCKS.
    """
    assert classify("grok-4") == "nonfree"
    assert classify("x-ai/grok-4-latest") == "nonfree"
    assert classify("grok-3") == "nonfree"


def test_default_deny_blocks_unlisted_unknown_models():
    """DEFAULT-DENY: a brand-new model we have never seen is nonfree, not 'unknown'."""
    assert classify("gemini-2.5-pro") == "nonfree"
    assert classify("o1") == "nonfree"
    assert classify("example-model") == "nonfree"
    assert classify("my-custom-free-endpoint") == "nonfree"


def test_known_free_models_still_pass():
    """No false positives on genuinely free allowlisted models."""
    assert classify("gpt-4o-mini") == "free"
    assert classify("llama-3.3-70b-versatile") == "free"
    assert classify("nousresearch/hermes-3-llama-3.1-405b:free") == "free"
    assert classify("deepseek/deepseek-chat") == "free"


def test_guard_module_has_no_fail_open_unknown_verdict():
    """Durability lock: the guard must NOT expose a fail-open 'unknown' verdict
    that would let unlisted paid models WARN-and-pass (exit 0)."""
    # finance/loop-free-aggregator's fail-open version returned 'unknown' for
    # unlisted models. The merged default-deny contract has no such verdict.
    assert "unknown" not in {classify(m) for m in
                             ["grok-4", "gemini-2.5-pro", "example-model", "o1", "gpt-4"]}
