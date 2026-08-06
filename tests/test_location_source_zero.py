"""Regression for #87: lat/lon 0.0 (ecuator/Greenwich) must survive parsing.

`or` treated 0.0 as falsy, so a device at the equator (lat 0) or on the
Greenwich meridian (lon 0) was dropped and never entered any geofence.
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

from lucidfence.core.location_source import LiveLocationSource


def test_lat_zero_survives():
    f = LiveLocationSource._extract_last_location
    assert f({"lastLocation": {"agent": {"latitude": 0.0, "longitude": -3.7}}}).get("lat") == 0.0
    assert f({"lastLocation": {"agent": {"latitude": 40.4, "longitude": 0.0}}}).get("lng") == 0.0


def test_both_axes_origin_survives():
    f = LiveLocationSource._extract_last_location
    loc = f({"lastLocation": {"agent": {"latitude": 0.0, "longitude": 0.0}}})
    assert loc["lat"] == 0.0 and loc["lng"] == 0.0


def test_flat_shape_lat_zero_survives():
    f = LiveLocationSource._extract_last_location
    assert f({"lastLocation": {"lat": 0.0, "lng": -3.7}}).get("lat") == 0.0


if __name__ == "__main__":
    test_lat_zero_survives()
    test_both_axes_origin_survives()
    test_flat_shape_lat_zero_survives()
    print("PASS: #87 location_source 0.0 coords survive")
