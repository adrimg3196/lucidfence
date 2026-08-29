"""Example free-tier provider plugin. Copy this file and change only PROVIDER.

IMPORTANT: /loop enforces a DEFAULT-DENY $0 rule (see lucidfence.core.free_tier).
Your `model` must be on the FREE_ALLOWLIST or it will be dropped from the
catalog at runtime and never called. Use a real free model (e.g. one of the
Hermes/Llama/Mixtral free tiers). Do NOT use `example-model` or any placeholder —
it is only whitelisted for this example file so the repo's own guard stays green;
a copy you rename and ship should point at a model you actually have a key for.
"""
PROVIDER = {
    "name": "example_free",
    "env": "LF_PROVIDER_EXAMPLE_API_KEY",
    "base": "https://api.example.invalid/v1",
    "model": "nousresearch/hermes-3-llama-3.1-405b:free",
}
