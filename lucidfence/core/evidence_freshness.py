"""Frescura y replay de evidencias locales.

Una señal puede ser verdadera en origen pero no ser utilizable para decisiones
sensibles si está caducada, fechada en el futuro, repetida o no trae reloj
confiable. Este módulo clasifica ese estado sin convertir unknown en false.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DEFAULT_TTL_SECONDS = 900
DEFAULT_CLOCK_SKEW_SECONDS = 60
DEFAULT_REPLAY_RETENTION_SECONDS = 86_400
DEFAULT_REPLAY_MAX_ENTRIES = 4096


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _epoch_seconds(value: str) -> int:
    dt = _parse_iso(value)
    return int(dt.timestamp()) if dt else 0


class ReplayRegistry:
    """Registro local acotado de nonces ya vistos.

    `record()` devuelve True si el nonce ya existía para el tipo de señal. En
    cualquier escritura poda primero por retención y después por tamaño,
    conservando los últimos observados de forma determinista.
    """

    def __init__(self, path: str | os.PathLike, *, max_entries: int = DEFAULT_REPLAY_MAX_ENTRIES,
                 retention_seconds: int = DEFAULT_REPLAY_RETENTION_SECONDS):
        self.path = Path(path)
        self.max_entries = max(1, int(max_entries or DEFAULT_REPLAY_MAX_ENTRIES))
        self.retention_seconds = max(0, int(retention_seconds or 0))

    def record(self, signal_type: str, nonce: str, *, observed_at: str) -> bool:
        signal_type = str(signal_type or "unknown")
        nonce = str(nonce or "")
        data = self._load()
        entries = self._pruned(data.get("entries") or [], observed_at)
        replayed = any(e.get("signal_type") == signal_type and e.get("nonce") == nonce for e in entries)
        if not replayed:
            entries.append({"signal_type": signal_type, "nonce": nonce, "observed_at": observed_at})
        entries = self._pruned(entries, observed_at)
        self._save({"entries": entries})
        return replayed

    def _load(self) -> dict:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"entries": []}
        return raw if isinstance(raw, dict) else {"entries": []}

    def _pruned(self, entries: list[dict], observed_at: str) -> list[dict]:
        now_s = _epoch_seconds(observed_at)
        keep = []
        for e in entries:
            if not isinstance(e, dict) or not e.get("nonce"):
                continue
            if self.retention_seconds and now_s:
                seen_s = _epoch_seconds(str(e.get("observed_at") or ""))
                if seen_s and now_s - seen_s > self.retention_seconds:
                    continue
            keep.append({
                "signal_type": str(e.get("signal_type") or "unknown"),
                "nonce": str(e.get("nonce")),
                "observed_at": str(e.get("observed_at") or ""),
            })
        keep.sort(key=lambda e: (e.get("observed_at") or "", e.get("signal_type") or "", e.get("nonce") or ""))
        return keep[-self.max_entries:]

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)


class EvidenceFreshnessVerifier:
    def __init__(self, windows: Optional[dict] = None, *, clock_skew_seconds: int = DEFAULT_CLOCK_SKEW_SECONDS,
                 replay_registry: Optional[ReplayRegistry] = None):
        self.windows = windows or {}
        self.clock_skew_seconds = max(0, int(clock_skew_seconds or 0))
        self.replay_registry = replay_registry

    def evaluate(self, *, signal_type: str, source: str, observed_at: str,
                 evidence_ts: Optional[str], nonce: Optional[str] = None) -> dict:
        signal_type = str(signal_type or "unknown")
        source = str(source or "unknown")
        cfg = self.windows.get(signal_type) or {}
        ttl = int(cfg.get("ttl_seconds", DEFAULT_TTL_SECONDS))
        require_nonce = bool(cfg.get("require_nonce", False))
        rule = f"ttl={ttl}s skew={self.clock_skew_seconds}s nonce={'required' if require_nonce else 'optional'}"
        observed = _parse_iso(observed_at)
        evidence = _parse_iso(evidence_ts)
        age = int((observed - evidence).total_seconds()) if observed and evidence else None

        status = "fresh"
        reason = f"{source}: evidencia fresca; edad {age}s; regla {rule}"
        if age is None:
            status = "unverifiable"
            reason = f"{source}: sin reloj confiable; regla {rule}"
        elif age < -self.clock_skew_seconds:
            status = "future"
            reason = f"{source}: timestamp futuro ({age}s); regla {rule}"
        elif age > ttl:
            status = "stale"
            reason = f"{source}: evidencia caducada; edad {age}s > ttl {ttl}s; regla {rule}"
        elif require_nonce and not nonce:
            status = "unverifiable"
            reason = f"{source}: nonce requerido ausente; edad {age}s; regla {rule}"
        elif nonce and self.replay_registry is not None:
            try:
                if self.replay_registry.record(signal_type, nonce, observed_at=observed_at):
                    status = "replayed"
                    reason = f"{source}: nonce repetido; edad {age}s; regla {rule}"
            except Exception as exc:  # fail-unknown, never authorize on registry failure
                status = "unverifiable"
                reason = f"{source}: registro replay no evaluable ({type(exc).__name__}); regla {rule}"

        return {
            "status": status,
            "source": source,
            "signal_type": signal_type,
            "observed_at": observed_at,
            "evidence_ts": evidence_ts,
            "age_seconds": age,
            "rule": rule,
            "reason": reason,
        }


def build_verifier(config: Optional[dict], data_dir: str | os.PathLike) -> EvidenceFreshnessVerifier:
    cfg = config or {}
    replay_cfg = cfg.get("replay") or {}
    registry = ReplayRegistry(
        Path(data_dir) / str(replay_cfg.get("path") or "evidence_replay_nonces.json"),
        max_entries=int(replay_cfg.get("max_entries", DEFAULT_REPLAY_MAX_ENTRIES)),
        retention_seconds=int(replay_cfg.get("retention_seconds", DEFAULT_REPLAY_RETENTION_SECONDS)),
    )
    return EvidenceFreshnessVerifier(
        cfg.get("signals") or {},
        clock_skew_seconds=int(cfg.get("clock_skew_seconds", DEFAULT_CLOCK_SKEW_SECONDS)),
        replay_registry=registry,
    )
