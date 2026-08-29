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

PAID EXCLUSIONS (the grok-4 false-negative fix, t_bdcf0cad)
-----------------------------------------------------------
Several model *families* have BOTH free and paid SKUs that share a substring
prefix (e.g. ``grok-4`` is paid but ``grok`` alone is a free-tier marker;
``deepseek-r1`` is paid but ``deepseek-chat`` is free). A bare family token in
``FREE_ALLOWLIST`` therefore over-blesses the paid sibling and creates a
fail-OPEN hole. Two rules close it:

  * ``grok`` was REMOVED from ``FREE_ALLOWLIST`` — a free Grok MUST carry the
    explicit ``:free`` suffix (e.g. ``x-ai/grok-3-mini:free``). Bare ``grok-4``
    / ``grok-3`` / ``grok-2`` are NON-free and are blocked.
  * ``PAID_EXCLUSIONS`` lists the specific paid sibling substrings. If a model
    id contains one of these, it is NON-free EVEN IF it also matches a family
    allow-token. This keeps the genuinely-free SKUs (``deepseek-chat``,
    ``mistralai/Mixtral-*``, ``command-r`` free tier, ``qwen`` open weights)
    working while blocking their paid siblings (``deepseek-r1``,
    ``mistral-large``, ``command-r-plus``, ``qwen-max`` ...).
"""
from __future__ import annotations

# Case-insensitive substring tokens. A model id is FREE iff it contains at
# least one of these tokens after lowercasing (and is not on PAID_EXCLUSIONS).
#
# DEFAULT-DENY: there is no catch-all, no "unknown = ok". If a model does not
# contain one of these exact tokens it is treated as NON-free and blocked/dropped
# (e.g. ``example-model``, ``my-custom-endpoint``, ``gemini-2.5-pro``,
# ``o1``, ``claude-3-5-haiku``, ``grok-4`` are all NON-free). To bless a new
# free model, add its token here AND in the offline detector's inline fallback.
FREE_ALLOWLIST = [
    # --- known free model families (substring, case-insensitive) ---
    ":free",          # OpenRouter / free-tier suffix (authoritative free marker)
    "gpt-4o-mini",    # OpenAI free mini tier
    "llama",          # Meta Llama family (all free tiers)
    "mixtral",        # Mistral Mixtral
    "mistral",        # Mistral (non-Mixtral free tiers)
    "hermes",         # Nous Hermes (free on OpenRouter)
    "deepseek",       # DeepSeek free chat (deepseek-chat); paid siblings below
    "qwen",           # Alibaba Qwen free / open-weight tiers
    "phi-",           # Microsoft Phi
    "gemma",          # Google Gemma
    "yi-",            # 01.AI Yi
    "command-r",      # Cohere Command-R (free tier); paid plus below
    "ministral",      # Mistral small free tiers
    "cohere",         # Cohere free tier
    "falcon",         # TII Falcon
    "stablelm",       # Stability StableLM
    # NOTE: "grok" is intentionally ABSENT — free Grok must use the ":free"
    # suffix. Bare grok-* (grok-4/grok-3/grok-2) are paid and must be blocked.
]

# Specific PAID sibling substrings that OVERRIDE a family allow-token. Adding a
# new paid SKU here is how we close a false-negative without dropping the free
# sibling. Order within is irrelevant; PAID_EXCLUSIONS is checked before
# FREE_ALLOWLIST in is_free_model().
PAID_EXCLUSIONS = [
    # xAI Grok — free variants MUST carry ":free"; these bare paid SKUs are blocked.
    "grok-4", "grok-3", "grok-2", "grok-beta", "grok-1",
    # DeepSeek paid reasoning/large tiers (deepseek-chat stays free).
    "deepseek-r1", "deepseek-v3", "deepseek-reasoner", "deepseek-coder-v2",
    # Mistral paid tiers (Mixtral + mistral free tiers stay free).
    "mistral-large", "mistral-medium", "mistral-next",
    # Cohere paid tiers (command-r free tier stays free).
    "command-r-plus", "command-r-08", "command-r-03", "command-nightfall",
    # Alibaba Qwen paid tiers (qwen open-weight / turbo free tiers stay free).
    "qwen-max", "qwen-plus", "qwen-turbo-max", "qwen2.5-max", "qwen2.5-plus",
    # Minimax / other non-free families occasionally matched by a broad token.
    "minimax", "abab", "step-", "glm-4-plus", "glm-4-air",
]


def is_free_model(model) -> bool:
    """Return True iff ``model`` is on the free allowlist (default-deny).

    Anything not matching is NON-free and must be blocked/dropped by the
    enforcement layers. Empty/non-string models are treated as NON-free so a
    missing ``model`` can never silently pass.

    Resolution order: an explicit ``:free`` suffix always wins (authoritative
    free marker); then any PAID_EXCLUSIONS substring forces NON-free even if a
    family token matches; then the FREE_ALLOWLIST family tokens apply.
    """
    if not isinstance(model, str) or not model:
        return False
    m = model.lower()
    # Authoritative free marker — any explicit :free designation is free.
    if ":free" in m:
        return True
    # Paid sibling substring overrides a family allow-token.
    for token in PAID_EXCLUSIONS:
        if token in m:
            return False
    for token in FREE_ALLOWLIST:
        if token in m:
            return True
    return False
