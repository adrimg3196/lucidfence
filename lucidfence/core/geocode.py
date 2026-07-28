"""Free geocoding for LucidFence — Nominatim / OpenStreetMap, no API key.

LucidFence defines geofences by address (e.g. "Calle Mayor 1, Madrid").
To turn that into coordinates we geocode it. We use the **public Nominatim
instance** (https://nominatim.openstreetmap.org) which is free, requires NO
API key, and only asks for a descriptive User-Agent + rate-limited usage
(max 1 req/s). Results are cached in a local SQLite so we never re-query
the same address.

This keeps the "100% free / 100% local" promise: no Google/MAPBOX
bill, no key. If the network is unavailable the helper returns None and the
caller falls back to coordinates the operator provided manually.

Security / design:
  - GET only, public endpoint, no secrets.
  - Polite: a real User-Agent and a 1.1s floor between calls.
  - Never raises: network/parse failures -> None.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import urllib.parse
import urllib.request

NOMINATIM = "https://nominatim.openstreetmap.org/search"
CACHE_DB = "data/geocode_cache.db"
_MIN_INTERVAL = 1.1  # Nominatim usage policy: <=1 req/s
_UA = "LucidFence/1.0 (self-hosted geofencing SaaS; contact: admin@local)"

_lock = threading.Lock()
_last_call = 0.0


def _ensure_db(path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS geocode ("
        "q TEXT PRIMARY KEY, lat REAL, lon REAL, label TEXT, ts INTEGER)"
    )
    con.commit()
    return con


def _cached(con, q: str):
    try:
        row = con.execute(
            "SELECT lat, lon, label FROM geocode WHERE q=?", (q,)
        ).fetchone()
        return row
    except Exception:
        return None


def _rate_limit():
    global _last_call
    with _lock:
        now = time.time()
        wait = _MIN_INTERVAL - (now - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()


def geocode(address: str, *, db_path: str = CACHE_DB,
           timeout: float = 10.0) -> dict | None:
    """Return {'lat': float, 'lon': float, 'label': str} or None.

    Caches by normalized address. Never raises.
    """
    address = (address or "").strip()
    if not address:
        return None
    q = address.lower()
    try:
        con = _ensure_db(db_path)
    except Exception:
        con = None
    if con is not None:
        hit = _cached(con, q)
        if hit:
            return {"lat": hit[0], "lon": hit[1], "label": hit[2]}

    _rate_limit()
    params = urllib.parse.urlencode({"q": address, "format": "json", "limit": "1"})
    url = f"{NOMINATIM}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        if not data:
            return None
        hit0 = data[0]
        lat = float(hit0["lat"])
        lon = float(hit0["lon"])
        label = hit0.get("display_name", address)
        if con is not None:
            try:
                con.execute(
                    "INSERT OR REPLACE INTO geocode VALUES (?,?,?,?,?)",
                    (q, lat, lon, label, int(time.time())),
                )
                con.commit()
            except Exception:
                pass
        return {"lat": lat, "lon": lon, "label": label}
    except Exception:
        return None
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass
