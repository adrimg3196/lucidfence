"""Free-tier allowlist for LucidFence's $0 (free-first) /loop rule.

This module is the SINGLE SOURCE OF TRUTH for what counts as a free model.
Both enforcement layers import it so they can never diverge:

  * PREVENTION  — ``loop_improve._provider_catalog()`` drops any model that is
                  NOT on this allowlist, so it can never reach the aggregator.
  * DETECTION   — ``scripts/loop_free_guard.py`` scans the *raw* merged catalog
                  with the same ``is_free_model()`` and blocks (exit 1) if any
                  reachable provider is not free.

DEFAULT-DENY. A model is free ONLY if it matches an entry below. Anything else
(an unlisted paid model such as ``gemini-2.5-pro``, ``o1``, ``claude-3-5-haiku``,
or a brand-new unknown id) is treated as NON-free and is blocked / dropped. This
is the opposite of a denylist: we do not try to enumerate every paid model, we
enumerate the free ones and fail closed on everything else.
"""
from __future__ import annotations

# Case-insensitive substring tokens. A model id is FREE iff it contains at
# least one of these tokens after lowercasing.
#
# DEFAULT-DENY: there is no catch-all, no "unknown = ok". If a model does not
# contain one of these exact tokens it is treated as NON-free and blocked/dropped
# (e.g. ``example-model``, ``my-custom-endpoint``, ``gemini-2.5-pro``,
# ``o1``, ``claude-3-5-haiku`` are all NON-free). To bless a new free model, add
# its token here AND in the offline detector's inline fallback.
FREE_ALLOWLIST = [
    # --- known free model families (substring, case-insensitive) ---
    ":free",          # OpenRouter / free-tier suffix
    "gpt-4o-mini",    # OpenAI free mini tier
    "llama",          # Meta Llama family (all free tiers)
    "mixtral",        # Mistral Mixtral
    "mistral",        # Mistral (non-Mixtral free tiers)
    "hermes",         # Nous Hermes (free on OpenRouter)
    "deepseek",       # DeepSeek free chat
    "qwen",           # Alibaba Qwen free tiers
    "phi-",           # Microsoft Phi
    "gemma",          # Google Gemma
    "grok",           # xAI Grok free tier
    "yi-",            # 01.AI Yi
    "command-r",      # Cohere Command-R (free tier)
    "ministral",      # Mistral small free tiers
    "cohere",         # Cohere free tier
    "falcon",         # TII Falcon
    "stablelm",       # Stability StableLM
]


def is_free_model(model) -> bool:
    """Return True iff ``model`` is on the free allowlist (default-deny).

    Anything not matching is NON-free and must be blocked/dropped by the
    enforcement layers. Empty/non-string models are treated as NON-free so a
    missing ``model`` can never silently pass.
    """
    if not isinstance(model, str) or not model:
        return False
    m = model.lower()
    for token in FREE_ALLOWLIST:
        if token in m:
            return True
    return False
