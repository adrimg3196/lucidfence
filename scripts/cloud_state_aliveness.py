#!/usr/bin/env python3
"""cloud_state_aliveness — dead-man check para el snapshot vivo de engine-cron.

engine-cron publica data/cloud_state.json en la rama de datos `cloud-state`
cada 15 min. Si engine-cron deja de publicar (el fallo #270: la vitrina de
Marketing y el daily-analysis de Product se rompen), este script lo detecta
mirando la antigüedad de `generated_at`.

Uso:
    python3 scripts/cloud_state_aliveness.py --max-age-minutes 60

Exit 0 = snapshot fresco (<= umbral). Exit 1 = STALE (no alcanzable, sin
generated_at, o antigüedad > umbral). Stdlib only — corre en CI sin pip.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
import urllib.request
from pathlib import Path

# URL canónica del snapshot vivo (en la rama cloud-state, nunca en main).
# Importada de scripts/check_vitrina.py, la fuente ÚNICA. Sin fallback literal:
# duplicar la URL aquí es exactamente la deriva que la fuente única evita, y si
# el import falla, fallar es lo correcto (fail-closed), no adivinar la URL.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_vitrina  # noqa: E402

CANONICAL_URL = check_vitrina.CANONICAL_URL

TIMEOUT_S = 30
# Un parpadeo de red no es un dead-man: sin reintentos, cada fallo transitorio
# del fetch abriría un incidente falso. 3 intentos con espera creciente.
FETCH_ATTEMPTS = 3
FETCH_BACKOFF_S = (5, 15)


def parse_generated_at(value: str) -> datetime.datetime:
    """Parsea el generated_at ISO (con o sin Z) a datetime UTC aware."""
    s = value.strip().replace("Z", "+00:00")
    return datetime.datetime.fromisoformat(s)


def age_minutes(generated_at: str, now: datetime.datetime | None = None) -> float:
    """Antigüedad en minutos del generated_at respecto a `now` (UTC)."""
    dt = parse_generated_at(generated_at)
    if dt.tzinfo is None:  # pragma: no cover - fromisoformat con Z ya es aware
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return (now - dt).total_seconds() / 60.0


def classify(
    data: dict | None,
    max_age_minutes: float,
    now: datetime.datetime | None = None,
) -> tuple[str, str]:
    """Devuelve ('fresh'|'stale', detail). Centro de la lógica, testeable."""
    if data is None:
        return "stale", "no se pudo obtener el snapshot (vitrina no alcanzable)"
    gen = data.get("generated_at")
    if not gen:
        return "stale", "generated_at ausente en cloud_state.json"
    try:
        age = age_minutes(gen, now=now)
    except Exception as exc:  # pragma: no cover - formato inesperado
        return "stale", f"generated_at no parseable: {gen!r} ({exc})"
    if age > max_age_minutes:
        return "stale", f"cloud-state tiene {age:.1f} min de antigüedad (> {max_age_minutes})"
    return "fresh", f"cloud-state fresco ({age:.1f} min)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age-minutes", type=float, default=60.0)
    ap.add_argument("--url", default=CANONICAL_URL)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    data = None
    ultimo_error: Exception | None = None
    for intento in range(FETCH_ATTEMPTS):
        if intento:
            time.sleep(FETCH_BACKOFF_S[min(intento - 1, len(FETCH_BACKOFF_S) - 1)])
        try:
            with urllib.request.urlopen(args.url, timeout=TIMEOUT_S) as r:
                raw = r.read()
            data = json.loads(raw)
            break
        except Exception as exc:
            ultimo_error = exc
            print(f"intento {intento + 1}/{FETCH_ATTEMPTS} fallido: "
                  f"{type(exc).__name__}: {exc}", file=sys.stderr)
    if data is None:
        print(f"STALE: no se pudo obtener el snapshot tras {FETCH_ATTEMPTS} "
              f"intentos: {type(ultimo_error).__name__}: {ultimo_error}")
        print("::error::engine-cron dead-man: vitrina cloud-state no alcanzable")
        return 1

    state, detail = classify(data, args.max_age_minutes)
    if state == "stale":
        print(f"STALE: {detail}")
        print("::error::engine-cron dead-man: cloud-state estancado")
        return 1
    if not args.quiet:
        print(f"OK: {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
