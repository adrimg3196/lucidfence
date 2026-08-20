"""`lucidfence apply`: políticas y geocercas como código (valida/diff/what-if/aplica).

Todo hermético en directorios temporales (--data-dir explícito) y capturando
stdout con redirect_stdout para funcionar bajo pytest y el runner honesto.
"""
from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from lucidfence import cli

CIRCLE = {"id": "hq", "name": "HQ Madrid", "type": "circle",
          "center": {"lat": 40.42, "lng": -3.7}, "radius_m": 300}
VIEJA = {"id": "vieja", "name": "Cerca obsoleta", "type": "circle",
         "center": {"lat": 41.0, "lng": -4.0}, "radius_m": 100}
NUEVA = {"id": "almacen", "name": "Almacén Norte", "type": "circle",
         "center": {"lat": 43.36, "lng": -5.85}, "radius_m": 250}
# Pajarita: (0,0)->(1,1)->(0,1)->(1,0) se auto-intersecta en el centro.
BOWTIE = {"id": "pajarita", "name": "Polígono roto", "type": "polygon",
          "coordinates": [{"lat": 0.0, "lng": 0.0}, {"lat": 1.0, "lng": 1.0},
                          {"lat": 0.0, "lng": 1.0}, {"lat": 1.0, "lng": 0.0}]}

POLICY_OK = {"id": "pol-qa", "name": "QA fuera de cerca", "description": "",
             "severity": "high", "enabled": True,
             "when": [{"field": "fence_state", "op": "eq", "value": "outside"}],
             "actions": [{"action": "notify", "params": {}}]}


def _apply(argv: list[str]) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main(["apply"] + argv)
    return rc, out.getvalue() + err.getvalue()


def _write(path: Path, payload) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_apply_subcommand_registered():
    args = cli.build_parser().parse_args(["apply", "--fences", "x.json"])
    assert args.func is cli.cmd_apply
    assert args.yes is False  # dry-run por defecto


def test_apply_requires_a_candidate_file():
    rc, out = _apply([])
    assert rc == 2
    assert "--fences o --policies" in out


def test_dry_run_valid_shows_diff_and_does_not_write():
    with tempfile.TemporaryDirectory() as td:
        data = Path(td) / "data"
        data.mkdir()
        live = _write(data / "fences.json", {"fences": [CIRCLE, VIEJA]})
        live_bytes = live.read_bytes()
        changed = dict(CIRCLE, radius_m=500)
        cand = _write(Path(td) / "cand.json", {"fences": [changed, NUEVA]})
        rc, out = _apply(["--fences", str(cand), "--data-dir", str(data)])
        assert rc == 0
        assert "+ almacen" in out
        assert "~ hq" in out
        assert "- vieja" in out  # eliminación detectada
        assert "sin histórico para simular" in out  # sin trails: lo dice, no inventa
        assert "dry-run: no se ha escrito nada" in out
        assert live.read_bytes() == live_bytes  # dry-run NO escribe


def test_self_intersecting_polygon_rejected_with_id():
    with tempfile.TemporaryDirectory() as td:
        data = Path(td) / "data"
        data.mkdir()
        cand = _write(Path(td) / "cand.json", {"fences": [BOWTIE]})
        rc, out = _apply(["--fences", str(cand), "--data-dir", str(data), "--yes"])
        assert rc == 1
        assert "pajarita" in out and "self-intersecting" in out
        assert not (data / "fences.json").exists()  # inválido: no se aplica nada


def test_malformed_policy_rejected_with_id():
    with tempfile.TemporaryDirectory() as td:
        data = Path(td) / "data"
        data.mkdir()
        bad_op = {"id": "pol-mala", "name": "op inválido",
                  "when": [{"field": "risk_score", "op": "equals", "value": 50}],
                  "actions": [{"action": "notify"}]}
        sin_when = {"id": "pol-vacia", "name": "sin when", "when": [],
                    "actions": [{"action": "lock"}]}
        cand = _write(Path(td) / "pols.json", [bad_op, sin_when])
        rc, out = _apply(["--policies", str(cand), "--data-dir", str(data)])
        assert rc == 1
        assert "pol-mala" in out and "'equals'" in out
        assert "pol-vacia" in out and "'when'" in out


def test_yes_applies_atomically_and_content_matches_candidate():
    with tempfile.TemporaryDirectory() as td:
        data = Path(td) / "data"
        data.mkdir()
        fcand = _write(Path(td) / "f.json", {"fences": [CIRCLE, NUEVA]})
        pcand = _write(Path(td) / "p.json", [POLICY_OK])
        rc, out = _apply(["--fences", str(fcand), "--policies", str(pcand),
                          "--data-dir", str(data), "--yes"])
        assert rc == 0
        assert "escrito" in out and "recarga" in out.lower()
        # escritura verbatim del candidato, sin residuo del tmp
        assert (data / "fences.json").read_text(encoding="utf-8") == fcand.read_text(encoding="utf-8")
        assert (data / "policies.json").read_text(encoding="utf-8") == pcand.read_text(encoding="utf-8")
        assert not list(data.glob("*.tmp"))


def test_what_if_replays_candidate_policy_over_trails():
    with tempfile.TemporaryDirectory() as td:
        data = Path(td) / "data"
        data.mkdir()
        rows = [{"device_id": "d1", "lat": 50.0, "lng": 8.0, "fence_state": "outside",
                 "ts": f"2026-08-18T10:0{i}:00Z"} for i in range(3)]
        (data / "trails.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        cand = _write(Path(td) / "p.json", [POLICY_OK])
        rc, out = _apply(["--policies", str(cand), "--data-dir", str(data)])
        assert rc == 0
        assert "pol-qa" in out and "habrían disparado 3 acciones" in out
        assert "3 puntos [exacto]" in out


def test_invalid_json_reports_filename_and_line():
    with tempfile.TemporaryDirectory() as td:
        data = Path(td) / "data"
        data.mkdir()
        cand = Path(td) / "roto.json"
        cand.write_text('{"fences": [', encoding="utf-8")
        rc, out = _apply(["--fences", str(cand), "--data-dir", str(data)])
        assert rc == 1
        assert "roto.json" in out and "JSON inválido" in out
