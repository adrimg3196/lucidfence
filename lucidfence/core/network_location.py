"""Windows / laptop geofencing lógico — ubicación gruesa por señal de red.

Los portátiles gestionados (Intune / Fleet / osquery) casi nunca traen GPS: no
hay CoreLocation, no hay chip de posición. Lo que un administrador de IT SÍ
conoce es la topología de su red: "nuestro bloque de IP de salida es la sede",
"la SSID CORP-MADRID es la oficina de Madrid", "esta BSSID es el AP de la sala
de servidores". Este módulo convierte ese conocimiento declarado por el operador
en una ubicación gruesa y honesta.

Principios (identidad del producto, no negociables):

- **Solo stdlib.** `ipaddress` para contención de CIDR, nada más.
- **Cero exfiltración.** No hay geoip de terceros, ni MaxMind, ni ninguna
  llamada de red. La ubicación sale ÚNICAMENTE de un mapeo declarado por el
  operador (firmas de red -> sitios con nombre). La señal de red de la flota
  jamás abandona la máquina.
- **Nunca se inventa una ubicación.** Si ninguna firma configurada casa con las
  señales del dispositivo, `resolve` devuelve None y el dispositivo se queda
  `unknown` (regla de producto — ver LOCATION_MATRIX.md §Reglas).
- **Precisión honesta.** El match arrastra `accuracy_m == radius_m` del sitio y
  `location_source="network"`, para que las políticas que exijan precisión fina
  se nieguen correctamente a actuar sobre un fix grueso.

Precedencia determinista cuando varios sitios casan (documentada aquí y probada
en tests/test_network_location.py):

  1. **Clase de señal, de la más específica a la menos:** un match por BSSID
     (un AP concreto) gana a un match por SSID (una red Wi-Fi) que gana a un
     match por CIDR de IP (un bloque de salida a internet).
  2. **Dentro de la misma clase de señal:** gana el sitio con `radius_m` MÁS
     PEQUEÑO (el más específico geográficamente).
  3. **Desempate final:** orden alfabético por nombre de sitio, para
     determinismo total.

Fail-closed: cualquier señal o sitio malformado nunca sale de `resolve` como
excepción; simplemente no casa.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Optional


# Clases de señal, de más específica (0) a menos específica (2). Un número más
# bajo gana en la precedencia.
_RANK_BSSID = 0
_RANK_SSID = 1
_RANK_IP = 2


def _normalize_bssid(value) -> Optional[str]:
    """Normaliza una MAC de AP a minúsculas separada por ':'.

    Acepta separadores ':' o '-' y las normaliza. Devuelve None si el valor no
    parece una MAC de 6 octetos hex (fail-closed: una BSSID basura no casa).
    """
    if not isinstance(value, str):
        return None
    raw = value.strip().lower().replace("-", ":")
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) != 6:
        return None
    for octet in parts:
        if len(octet) not in (1, 2):
            return None
        try:
            int(octet, 16)
        except ValueError:
            return None
    return ":".join(o.zfill(2) for o in parts)


def _normalize_ssid(value) -> Optional[str]:
    """SSID normalizada para comparación exacta case-insensitive."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    return s.casefold()


@dataclass
class NetworkSite:
    """Un sitio con nombre y las firmas de red que lo identifican.

    Construir un NetworkSite valida sus campos y NORMALIZA sus reglas de match.
    Un sitio malformado (lat/lng/radio fuera de rango, CIDR ilegible) se rechaza
    lanzando ValueError en `__post_init__`; el resolver captura eso y lo descarta
    con un registro, sin romperse (igual que osquery_posture degrada).
    """

    name: str
    lat: float
    lng: float
    radius_m: float
    ip_cidrs: list[str] = field(default_factory=list)
    ssids: list[str] = field(default_factory=list)
    bssids: list[str] = field(default_factory=list)
    # Normalizados en __post_init__ (no se pasan al construir).
    _networks: list = field(default_factory=list, repr=False)
    _ssid_set: set = field(default_factory=set, repr=False)
    _bssid_set: set = field(default_factory=set, repr=False)

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("network_site.name es obligatorio")
        self.name = self.name.strip()
        try:
            self.lat = float(self.lat)
            self.lng = float(self.lng)
            self.radius_m = float(self.radius_m)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"network_site '{self.name}': lat/lng/radius no numéricos: {exc}")
        if not (-90.0 <= self.lat <= 90.0):
            raise ValueError(f"network_site '{self.name}': lat fuera de [-90,90]: {self.lat}")
        if not (-180.0 <= self.lng <= 180.0):
            raise ValueError(f"network_site '{self.name}': lng fuera de [-180,180]: {self.lng}")
        if not (self.radius_m > 0):
            raise ValueError(f"network_site '{self.name}': radius_m debe ser > 0: {self.radius_m}")

        networks = []
        for cidr in self.ip_cidrs or []:
            if not isinstance(cidr, str) or not cidr.strip():
                continue
            try:
                networks.append(ipaddress.ip_network(cidr.strip(), strict=False))
            except (ValueError, TypeError):
                # Un CIDR ilegible se descarta, no invalida el sitio entero:
                # las demás firmas (SSID/BSSID/otros CIDR) siguen sirviendo.
                continue
        self._networks = networks

        ssid_set = set()
        for ssid in self.ssids or []:
            norm = _normalize_ssid(ssid)
            if norm is not None:
                ssid_set.add(norm)
        self._ssid_set = ssid_set

        bssid_set = set()
        for bssid in self.bssids or []:
            norm = _normalize_bssid(bssid)
            if norm is not None:
                bssid_set.add(norm)
        self._bssid_set = bssid_set

    # --- matchers individuales: devuelven bool, nunca lanzan ---
    def matches_bssid(self, bssid: Optional[str]) -> bool:
        norm = _normalize_bssid(bssid)
        return norm is not None and norm in self._bssid_set

    def matches_ssid(self, ssid: Optional[str]) -> bool:
        norm = _normalize_ssid(ssid)
        return norm is not None and norm in self._ssid_set

    def matches_ip(self, ip: Optional[str]) -> bool:
        if not isinstance(ip, str) or not ip.strip() or not self._networks:
            return False
        try:
            addr = ipaddress.ip_address(ip.strip())
        except (ValueError, TypeError):
            return False
        for net in self._networks:
            try:
                if addr in net:
                    return True
            except (TypeError, ValueError):
                continue
        return False


class NetworkLocationResolver:
    """Resuelve señales de red -> ubicación gruesa contra sitios declarados.

    Se construye desde un dict de config `{"network_sites": [ {...}, ... ]}`.
    Sitios malformados se descartan (se registran en `skipped`) sin romper la
    construcción, replicando cómo osquery_posture degrada ante entrada mala.
    """

    def __init__(self, config: Optional[dict] = None):
        config = config if isinstance(config, dict) else {}
        raw_sites = config.get("network_sites")
        if not isinstance(raw_sites, list):
            raw_sites = []
        self.sites: list[NetworkSite] = []
        self.skipped: list[dict] = []
        for entry in raw_sites:
            if not isinstance(entry, dict):
                self.skipped.append({"entry": repr(entry)[:120], "error": "no es un objeto"})
                continue
            try:
                site = NetworkSite(
                    name=entry.get("name"),
                    lat=entry.get("lat"),
                    lng=entry.get("lng"),
                    radius_m=entry.get("radius_m"),
                    ip_cidrs=entry.get("ip_cidrs") or [],
                    ssids=entry.get("ssids") or [],
                    bssids=entry.get("bssids") or [],
                )
            except (ValueError, TypeError) as exc:
                self.skipped.append({
                    "entry": str(entry.get("name") or repr(entry)[:120]),
                    "error": f"{type(exc).__name__}: {exc}",
                })
                continue
            self.sites.append(site)

    @property
    def configured(self) -> bool:
        """True solo si hay al menos un sitio válido; guarda la inercia."""
        return bool(self.sites)

    def resolve(self, signals: dict) -> Optional[dict]:
        """Devuelve los campos de ubicación del sitio que mejor casa, o None.

        `signals` puede traer `ip` (IP pública/salida), `ssid`, `bssid`. Nunca
        lanza: entrada malformada simplemente no casa. Aplica la precedencia
        documentada en el docstring del módulo.
        """
        if not isinstance(signals, dict):
            return None
        ip = signals.get("ip")
        ssid = signals.get("ssid")
        bssid = signals.get("bssid")

        best = None  # tupla (rank, radius_m, name, site)
        for site in self.sites:
            rank = None
            try:
                if site.matches_bssid(bssid):
                    rank = _RANK_BSSID
                elif site.matches_ssid(ssid):
                    rank = _RANK_SSID
                elif site.matches_ip(ip):
                    rank = _RANK_IP
            except Exception:
                # Fail-closed absoluto: cualquier sorpresa en el matching de un
                # sitio se trata como "no casa", jamás sale de resolve.
                rank = None
            if rank is None:
                continue
            candidate = (rank, site.radius_m, site.name, site)
            if best is None or candidate[:3] < best[:3]:
                best = candidate

        if best is None:
            return None
        site = best[3]
        return {
            "lat": site.lat,
            "lng": site.lng,
            "accuracy_m": site.radius_m,
            "location_source": "network",
            "site": site.name,
        }
