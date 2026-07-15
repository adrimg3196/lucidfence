"""Tenant-local BYO AI provider configuration and OpenAI-compatible client.

This module has no third-party dependencies. Secrets are stored with mode 0600,
never returned by public status functions, and never copied to process globals.
"""
from __future__ import annotations

import json
import os
import ssl
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

CONFIG_FILE = "ai_provider.json"
ENV_FILE = ".env"
ENV_KEY = "LUCIDFENCE_AI_API_KEY"

PRESETS = [
    {"id": "disabled", "name": "Sin IA", "base_url": "", "key_optional": True},
    {"id": "openai", "name": "OpenAI", "base_url": "https://api.openai.com/v1", "key_optional": False},
    {"id": "ollama", "name": "Ollama local", "base_url": "http://127.0.0.1:11434/v1", "key_optional": True},
    {"id": "lmstudio", "name": "LM Studio local", "base_url": "http://127.0.0.1:1234/v1", "key_optional": True},
    {"id": "custom", "name": "OpenAI-compatible", "base_url": "", "key_optional": True},
]


def _secure_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)


def _load_config(root: Path) -> Dict[str, Any]:
    try:
        data = json.loads((Path(root) / CONFIG_FILE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _read_env(root: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    path = Path(root) / ENV_FILE
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def _valid_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme in ("http", "https") and bool(parsed.hostname) and not parsed.username
    except ValueError:
        return False


def _mask(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 8:
        return "•" * len(secret)
    return secret[:4] + "•" * max(4, len(secret) - 8) + secret[-4:]


def save(root: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    root = Path(root)
    enabled = bool(payload.get("enabled"))
    provider = str(payload.get("provider") or ("custom" if enabled else "disabled")).strip().lower()
    base_url = str(payload.get("base_url") or "").strip().rstrip("/")
    model = str(payload.get("model") or "").strip()
    if enabled:
        if not _valid_url(base_url):
            return {"ok": False, "error": "base_url debe usar http o https y tener un host válido"}
        if not model:
            return {"ok": False, "error": "model es obligatorio cuando la IA está activa"}
    config = {"enabled": enabled, "provider": provider, "base_url": base_url, "model": model}
    env = _read_env(root)
    if "api_key" in payload:
        supplied = str(payload.get("api_key") or "").strip()
        if "\n" in supplied or "\r" in supplied:
            return {"ok": False, "error": "api_key contiene caracteres no permitidos"}
        if supplied:
            env[ENV_KEY] = supplied
        elif payload.get("clear_api_key"):
            env.pop(ENV_KEY, None)
    # All validation happened above; now commit both tenant-local files.
    _secure_write(root / CONFIG_FILE, json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    _secure_write(root / ENV_FILE, "".join("%s=%s\n" % item for item in sorted(env.items())))
    return {"ok": True, **status(root)}


def status(root: Path) -> Dict[str, Any]:
    config = _load_config(Path(root))
    key = _read_env(Path(root)).get(ENV_KEY, "")
    enabled = bool(config.get("enabled"))
    return {
        "configured": enabled and bool(config.get("base_url")) and bool(config.get("model")),
        "enabled": enabled,
        "provider": config.get("provider", "disabled"),
        "base_url": config.get("base_url", ""),
        "model": config.get("model", ""),
        "key_configured": bool(key),
        "masked_key": _mask(key),
        "presets": PRESETS,
    }


def _request(root: Path, method: str, suffix: str, payload: Optional[Dict[str, Any]] = None,
             timeout: int = 20) -> Dict[str, Any]:
    config = _load_config(Path(root))
    if not config.get("enabled"):
        return {"ok": False, "status": 503, "error": "proveedor AI desactivado"}
    base_url = str(config.get("base_url") or "").rstrip("/")
    if not _valid_url(base_url):
        return {"ok": False, "status": 400, "error": "base_url AI inválida"}
    key = _read_env(Path(root)).get(ENV_KEY, "")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(base_url + suffix, data=body, headers=headers, method=method)
    try:
        context = ssl.create_default_context()
        with urlopen(request, timeout=timeout, context=context) as response:
            raw = response.read(2_000_000).decode("utf-8", "replace")
            data = json.loads(raw) if raw else {}
            return {"ok": True, "status": int(response.status), "data": data}
    except HTTPError as exc:
        try:
            detail = exc.read(2048).decode("utf-8", "replace")
        except Exception:
            detail = ""
        if key:
            detail = detail.replace(key, "[REDACTED]")
        return {"ok": False, "status": int(exc.code), "error": "provider HTTP %s" % exc.code,
                "detail": detail[:500]}
    except (URLError, TimeoutError, ConnectionError, OSError) as exc:
        return {"ok": False, "status": 0, "error": "no se pudo conectar con el proveedor AI",
                "category": type(exc).__name__}
    except (ValueError, TypeError) as exc:
        return {"ok": False, "status": 502, "error": "respuesta AI no válida",
                "category": type(exc).__name__}


def test_connection(root: Path) -> Dict[str, Any]:
    result = _request(Path(root), "GET", "/models", timeout=10)
    if not result.get("ok"):
        return result
    data = result.get("data") or {}
    models = [str(item.get("id")) for item in data.get("data", []) if isinstance(item, dict) and item.get("id")]
    return {"ok": True, "status": result.get("status"), "models": models[:100]}


def test_values(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Test unsaved form values without mutating the tenant directory."""
    with tempfile.TemporaryDirectory(prefix="lucidfence-ai-test-") as tmp:
        transient = dict(payload)
        transient["enabled"] = True
        saved = save(Path(tmp), transient)
        if not saved.get("ok"):
            return saved
        return test_connection(Path(tmp))


def chat(root: Path, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = _load_config(Path(root))
    opts = dict(options or {})
    payload: Dict[str, Any] = {
        "model": config.get("model", ""),
        "messages": messages,
        "stream": False,
        "temperature": float(opts.get("temperature", 0.2)),
        "max_tokens": int(opts.get("max_tokens", 1000)),
    }
    result = _request(Path(root), "POST", "/chat/completions", payload, timeout=60)
    if not result.get("ok"):
        return result
    response = result.get("data") or {}
    choices = response.get("choices") or []
    text = ""
    if choices and isinstance(choices[0], dict):
        text = str((choices[0].get("message") or {}).get("content") or "")
    if not text:
        return {"ok": False, "status": 502, "error": "el proveedor no devolvió choices[0].message.content"}
    return {"ok": True, "status": result.get("status"), "text": text, "response": response}
