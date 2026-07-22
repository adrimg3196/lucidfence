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

Run `python3 loop_improve.py --dry-run` to see the discovered providers whose key
is configured. The dashboard exposes only names and quality metrics, never keys.
