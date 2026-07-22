#!/usr/bin/env python3
"""Deterministic 10k-device geofence kernel benchmark."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time

from core.geo import Point, haversine_m


def benchmark(devices: int = 10_000, rounds: int = 5) -> dict:
    if devices < 1 or rounds < 1:
        raise ValueError("devices and rounds must be positive")
    fleet = [(40.4168 + math.sin(i) * .8, -3.7038 + math.cos(i) * .8) for i in range(devices)]
    samples = []
    inside = 0
    for _ in range(rounds):
        start = time.perf_counter()
        center = Point(40.4168, -3.7038)
        inside = sum(1 for lat, lng in fleet if haversine_m(Point(lat, lng), center) <= 50_000)
        samples.append(time.perf_counter() - start)
    ordered = sorted(samples)
    p95 = ordered[min(len(ordered) - 1, math.ceil(len(ordered) * .95) - 1)]
    return {"devices": devices, "rounds": rounds, "inside": inside,
            "mean_seconds": round(statistics.mean(samples), 6), "p95_seconds": round(p95, 6),
            "devices_per_second": round(devices / statistics.mean(samples)),
            "threshold_seconds": 2.0, "pass": p95 < 2.0}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--devices", type=int, default=10_000); parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args(); result = benchmark(args.devices, args.rounds)
    print(json.dumps(result, indent=2)); return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
