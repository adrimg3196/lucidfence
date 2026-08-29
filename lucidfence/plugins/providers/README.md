# LucidFence provider plugins

Add one `.py` file exposing a plain `PROVIDER` dictionary:

```python
PROVIDER = {
    "name": "my_free_provider",
    "env": "LF_PROVIDER_MY_FREE_PROVIDER_API_KEY",
    "base": "https://provider.example/v1",
    "model": "model-id",
}
```

Rules:
- HTTPS only.
- Secrets are read from the named environment variable; never put keys here.
- Filenames beginning with `_` are ignored.
- Invalid plugins are skipped and cannot break the local app.
- Duplicate names are first-wins, so plugins cannot silently replace built-ins.
- **Default-deny free-tier only.** The `/loop` aggregator enforces a `$0` rule
  with a curated **free allowlist** (`lucidfence/core/free_tier.py`). Any provider
  whose `model` is NOT on that allowlist — including unknown/new models such as
  `gemini-2.5-pro`, `o1`, `o3-mini`, `claude-3-5-haiku`, or any paid tier
  (`claude-opus-*`, `gpt-4` non-mini, `gpt-5`, `sonnet`) — is **dropped** from the
  catalog at runtime and will never be called (fail-closed). Use a free model that
  is on the allowlist (`gpt-4o-mini`, `llama-*`, `mixtral`, `hermes-*:free`, …).
  Run `python3 scripts/loop_free_guard.py` to verify no non-free model is reachable;
  it runs as a CI check on every PR that touches `loop_improve.py` or
  `plugins/providers/`.

Run `python3 loop_improve.py --dry-run` to see the discovered providers whose key
is configured. The dashboard exposes only names and quality metrics, never keys.
