"""Contract tests for network_location.py — geofencing lógico por red (#6).

Cubren: contención de CIDR, SSID case-insensitive, normalización de BSSID,
precedencia (bssid>ssid>ip, radio menor gana, desempate por nombre), rechazo de
sitios malformados, no-match -> None, accuracy_m == radius, entrada envenenada
que jamás lanza ni fabrica ubicación, y la enriquecimiento en la capa de source
(inerte cuando no hay network_sites).
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

from lucidfence.core.network_location import NetworkSite, NetworkLocationResolver
from lucidfence.core.location_source import LocationReport, build_location_source


# ------------------------------------------------------------------ NetworkSite

def test_site_normalizes_and_validates():
    s = NetworkSite(name="HQ", lat=40.4, lng=-3.7, radius_m=500,
                    ip_cidrs=["203.0.113.0/24"], ssids=["Corp-WiFi"],
                    bssids=["AA-BB-CC-DD-EE-FF"])
    assert s.name == "HQ"
    assert s.matches_ip("203.0.113.55")
    assert s.matches_ssid("corp-wifi")  # case-insensitive
    assert s.matches_bssid("aa:bb:cc:dd:ee:ff")  # normalized from dash form


def test_site_rejects_bad_lat():
    for bad in (91.0, -90.1, "north"):
        try:
            NetworkSite(name="X", lat=bad, lng=0.0, radius_m=10)
            assert False, f"lat {bad!r} debería ser rechazado"
        except (ValueError, TypeError):
            pass


def test_site_rejects_bad_lng():
    for bad in (180.5, -181.0):
        try:
            NetworkSite(name="X", lat=0.0, lng=bad, radius_m=10)
            assert False, f"lng {bad!r} debería ser rechazado"
        except (ValueError, TypeError):
            pass


def test_site_rejects_bad_radius():
    for bad in (0, -5, "big"):
        try:
            NetworkSite(name="X", lat=0.0, lng=0.0, radius_m=bad)
            assert False, f"radius {bad!r} debería ser rechazado"
        except (ValueError, TypeError):
            pass


# --------------------------------------------------------------- CIDR matching

def test_cidr_containment_match():
    r = NetworkLocationResolver({"network_sites": [
        {"name": "Madrid", "lat": 40.4, "lng": -3.7, "radius_m": 800,
         "ip_cidrs": ["198.51.100.0/24"]},
    ]})
    out = r.resolve({"ip": "198.51.100.200"})
    assert out is not None
    assert out["site"] == "Madrid"
    assert out["location_source"] == "network"
    assert out["accuracy_m"] == 800
    # fuera del bloque -> None
    assert r.resolve({"ip": "198.51.101.1"}) is None


def test_cidr_ipv6_and_host_bits():
    # strict=False acepta host bits (ej. 203.0.113.5/24) y también IPv6.
    r = NetworkLocationResolver({"network_sites": [
        {"name": "V6", "lat": 1.0, "lng": 1.0, "radius_m": 1000,
         "ip_cidrs": ["203.0.113.5/24", "2001:db8::/32"]},
    ]})
    assert r.resolve({"ip": "203.0.113.9"})["site"] == "V6"
    assert r.resolve({"ip": "2001:db8::1"})["site"] == "V6"


# --------------------------------------------------------------- SSID matching

def test_ssid_case_insensitive():
    r = NetworkLocationResolver({"network_sites": [
        {"name": "Office", "lat": 10.0, "lng": 10.0, "radius_m": 300,
         "ssids": ["CORP-WIFI"]},
    ]})
    assert r.resolve({"ssid": "corp-wifi"})["site"] == "Office"
    assert r.resolve({"ssid": "Corp-WiFi"})["site"] == "Office"
    assert r.resolve({"ssid": "guest"}) is None


# --------------------------------------------------------------- BSSID matching

def test_bssid_normalization():
    r = NetworkLocationResolver({"network_sites": [
        {"name": "AP1", "lat": 5.0, "lng": 5.0, "radius_m": 50,
         "bssids": ["AA:BB:CC:00:11:22"]},
    ]})
    # dash form, uppercase, unpadded octets all normalize to the same key
    assert r.resolve({"bssid": "aa-bb-cc-00-11-22"})["site"] == "AP1"
    assert r.resolve({"bssid": "AA:BB:CC:0:11:22"})["site"] == "AP1"
    assert r.resolve({"bssid": "ff:ff:ff:ff:ff:ff"}) is None


# ----------------------------------------------------------------- precedence

def test_precedence_bssid_beats_ssid_beats_ip():
    # Tres sitios que casarían por distintas señales; el mismo dispositivo trae
    # las tres. Debe ganar el match por BSSID.
    r = NetworkLocationResolver({"network_sites": [
        {"name": "ByIP", "lat": 1.0, "lng": 1.0, "radius_m": 10,
         "ip_cidrs": ["10.0.0.0/8"]},
        {"name": "BySSID", "lat": 2.0, "lng": 2.0, "radius_m": 10,
         "ssids": ["net"]},
        {"name": "ByBSSID", "lat": 3.0, "lng": 3.0, "radius_m": 9999,
         "bssids": ["aa:aa:aa:aa:aa:aa"]},
    ]})
    out = r.resolve({"ip": "10.1.2.3", "ssid": "net", "bssid": "aa:aa:aa:aa:aa:aa"})
    assert out["site"] == "ByBSSID"  # más específica gana aunque su radio sea enorme
    # Sin la BSSID, gana SSID sobre IP.
    out2 = r.resolve({"ip": "10.1.2.3", "ssid": "net"})
    assert out2["site"] == "BySSID"


def test_precedence_smaller_radius_wins_same_class():
    r = NetworkLocationResolver({"network_sites": [
        {"name": "Wide", "lat": 1.0, "lng": 1.0, "radius_m": 1000,
         "ip_cidrs": ["192.0.2.0/24"]},
        {"name": "Tight", "lat": 2.0, "lng": 2.0, "radius_m": 100,
         "ip_cidrs": ["192.0.2.0/25"]},
    ]})
    out = r.resolve({"ip": "192.0.2.10"})
    assert out["site"] == "Tight"
    assert out["accuracy_m"] == 100


def test_precedence_name_tiebreak():
    r = NetworkLocationResolver({"network_sites": [
        {"name": "Bravo", "lat": 1.0, "lng": 1.0, "radius_m": 100,
         "ssids": ["x"]},
        {"name": "Alpha", "lat": 2.0, "lng": 2.0, "radius_m": 100,
         "ssids": ["x"]},
    ]})
    # misma clase de señal y mismo radio -> desempate alfabético por nombre
    assert r.resolve({"ssid": "x"})["site"] == "Alpha"


# --------------------------------------------------------- malformed / no match

def test_malformed_sites_skipped_not_crash():
    r = NetworkLocationResolver({"network_sites": [
        {"name": "Good", "lat": 1.0, "lng": 1.0, "radius_m": 100, "ssids": ["ok"]},
        {"name": "BadLat", "lat": 999, "lng": 1.0, "radius_m": 100, "ssids": ["nope"]},
        {"name": "BadRadius", "lat": 1.0, "lng": 1.0, "radius_m": -1, "ssids": ["nope"]},
        "not-a-dict",
        {"lat": 1.0, "lng": 1.0, "radius_m": 100},  # sin nombre
    ]})
    assert len(r.sites) == 1
    assert r.sites[0].name == "Good"
    assert len(r.skipped) == 4
    assert r.resolve({"ssid": "ok"})["site"] == "Good"
    assert r.resolve({"ssid": "nope"}) is None


def test_no_match_returns_none():
    r = NetworkLocationResolver({"network_sites": [
        {"name": "HQ", "lat": 1.0, "lng": 1.0, "radius_m": 100,
         "ip_cidrs": ["203.0.113.0/24"]},
    ]})
    assert r.resolve({"ip": "8.8.8.8"}) is None
    assert r.resolve({}) is None
    assert r.resolve({"ssid": None, "bssid": None, "ip": None}) is None


def test_accuracy_equals_radius():
    r = NetworkLocationResolver({"network_sites": [
        {"name": "R", "lat": 1.0, "lng": 1.0, "radius_m": 275.5, "ssids": ["r"]},
    ]})
    assert r.resolve({"ssid": "r"})["accuracy_m"] == 275.5


def test_empty_config_never_matches():
    assert NetworkLocationResolver({}).resolve({"ip": "1.2.3.4"}) is None
    assert NetworkLocationResolver(None).configured is False
    assert NetworkLocationResolver({"network_sites": []}).configured is False


# ----------------------------------------------------------- poisoned input

def test_poisoned_input_never_raises_never_fabricates():
    r = NetworkLocationResolver({"network_sites": [
        {"name": "HQ", "lat": 40.0, "lng": -3.0, "radius_m": 500,
         "ip_cidrs": ["203.0.113.0/24"], "ssids": ["corp"],
         "bssids": ["aa:bb:cc:dd:ee:ff"]},
    ]})
    garbage_signals = [
        {"ip": "not-an-ip"},
        {"ip": "999.999.999.999"},
        {"ip": ""},
        {"ip": "10.0.0.1; DROP TABLE devices;--"},
        {"ip": "192.168.1.1"},        # IP privada, no declarada -> no casa
        {"ip": "127.0.0.1"},
        {"ssid": "'; DROP TABLE --"},
        {"ssid": ""},
        {"ssid": 12345},              # tipo equivocado
        {"bssid": "zz:zz:zz:zz:zz:zz"},
        {"bssid": "aa:bb:cc"},        # muy corta
        {"bssid": "../../etc/passwd"},
        {"ip": None, "ssid": None, "bssid": None},
        {"ip": ["1.2.3.4"]},          # tipo equivocado
        {"ssid": {"nested": "obj"}},
        {"bssid": 3.14159},
    ]
    for sig in garbage_signals:
        out = r.resolve(sig)  # jamás debe lanzar
        assert out is None, f"entrada envenenada fabricó ubicación: {sig!r} -> {out!r}"
    # Y una entrada de tipo totalmente equivocado tampoco lanza.
    assert r.resolve("not-a-dict") is None
    assert r.resolve(None) is None
    assert r.resolve(42) is None


# ----------------------------------------------------------- enrichment layer

def _report(**kw):
    base = dict(device_id="d1", name="laptop-01", platform="windows",
                lat=None, lng=None)
    base.update(kw)
    return LocationReport(**base)


class _StubSource:
    """Fuente mínima que devuelve reports preparados (sin red)."""
    def __init__(self, reports):
        self._reports = reports
        self.last_error = None

    def fetch(self):
        return list(self._reports)

    def fetch_one(self, device_id):
        for r in self._reports:
            if r.device_id == device_id:
                return r
        return None


def test_enrichment_fills_coordinateless_report_from_ip():
    from lucidfence.core.location_source import _NetworkEnrichedSource
    resolver = NetworkLocationResolver({"network_sites": [
        {"name": "Madrid-HQ", "lat": 40.4168, "lng": -3.7038, "radius_m": 600,
         "ip_cidrs": ["198.51.100.0/24"]},
    ]})
    rep = _report(ip="198.51.100.42")
    src = _NetworkEnrichedSource(_StubSource([rep]), resolver)
    out = src.fetch()[0]
    assert out.lat == 40.4168 and out.lng == -3.7038
    assert out.accuracy_m == 600
    assert out.location_source == "network"


def test_enrichment_reads_ssid_bssid_from_raw():
    from lucidfence.core.location_source import _NetworkEnrichedSource
    resolver = NetworkLocationResolver({"network_sites": [
        {"name": "AP-Room", "lat": 1.0, "lng": 2.0, "radius_m": 30,
         "bssids": ["aa:bb:cc:dd:ee:ff"]},
    ]})
    rep = _report(raw={"bssid": "AA-BB-CC-DD-EE-FF"})
    src = _NetworkEnrichedSource(_StubSource([rep]), resolver)
    out = src.fetch()[0]
    assert out.location_source == "network"
    assert out.lat == 1.0 and out.lng == 2.0


def test_enrichment_does_not_overwrite_real_gps():
    from lucidfence.core.location_source import _NetworkEnrichedSource
    resolver = NetworkLocationResolver({"network_sites": [
        {"name": "HQ", "lat": 40.0, "lng": -3.0, "radius_m": 500,
         "ip_cidrs": ["198.51.100.0/24"]},
    ]})
    rep = _report(lat=12.34, lng=56.78, ip="198.51.100.42",
                  accuracy_m=8.0, location_source="applivery")
    src = _NetworkEnrichedSource(_StubSource([rep]), resolver)
    out = src.fetch()[0]
    assert out.lat == 12.34 and out.lng == 56.78
    assert out.accuracy_m == 8.0
    assert out.location_source == "applivery"  # intacto


def test_enrichment_no_match_leaves_report_unknown():
    from lucidfence.core.location_source import _NetworkEnrichedSource
    resolver = NetworkLocationResolver({"network_sites": [
        {"name": "HQ", "lat": 40.0, "lng": -3.0, "radius_m": 500,
         "ip_cidrs": ["198.51.100.0/24"]},
    ]})
    rep = _report(ip="8.8.8.8")
    src = _NetworkEnrichedSource(_StubSource([rep]), resolver)
    out = src.fetch()[0]
    assert out.lat is None and out.lng is None
    assert out.location_source == "applivery"  # default, sin inventar


def test_build_source_inert_without_network_sites():
    # Sin network_sites, build_location_source devuelve la fuente SIN envolver:
    # comportamiento byte-idéntico (no es _NetworkEnrichedSource).
    src_plain = build_location_source("simulation", "org", sim_seed_path="data/fleet_seed.json")
    src_cfg = build_location_source("simulation", "org", sim_seed_path="data/fleet_seed.json",
                                    network_cfg={"other_key": 1})
    src_empty = build_location_source("simulation", "org", sim_seed_path="data/fleet_seed.json",
                                      network_cfg={"network_sites": []})
    for s in (src_plain, src_cfg, src_empty):
        assert type(s).__name__ == "SimulationLocationSource"


def test_build_source_wraps_when_network_sites_present():
    src = build_location_source(
        "simulation", "org", sim_seed_path="data/fleet_seed.json",
        network_cfg={"network_sites": [
            {"name": "HQ", "lat": 1.0, "lng": 1.0, "radius_m": 100, "ssids": ["x"]},
        ]},
    )
    assert type(src).__name__ == "_NetworkEnrichedSource"
    # Delegación transparente: last_error sigue accesible.
    assert src.last_error is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
