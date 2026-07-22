"""Interactive local LucidFence shell (stdlib-only)."""
from __future__ import annotations

import cmd
import json
import shlex
from pathlib import Path
from typing import Callable

import roadmap_tooling
from core.location_source import SimulationLocationSource
from core.product import build_product


class LucidFenceShell(cmd.Cmd):
    intro = "LucidFence shell · escribe help o ? · exit para salir"
    prompt = "lf> "

    def __init__(self, root: str | Path | None = None, output: Callable[[str], None] = print):
        super().__init__()
        self.root = Path(root or Path(__file__).resolve().parents[1])
        self.output = output

    def do_roadmap(self, arg: str) -> None:
        """roadmap [phase] — muestra el roadmap local y su progreso."""
        data = roadmap_tooling.load_roadmap()
        self.output(roadmap_tooling.format_roadmap(data, phase=arg.strip() or None) if data else "roadmap no disponible")

    def do_simulate(self, arg: str) -> None:
        """simulate [cycles] — ejecuta ciclos del simulador sin red."""
        try:
            cycles = max(1, min(100, int(arg.strip() or "1")))
        except ValueError:
            self.output("ERROR: cycles debe ser entero")
            return
        source = SimulationLocationSource(str(self.root / "data" / "fleet_seed.json"), org_id="shell")
        rows = []
        for _ in range(cycles):
            rows = source.fetch()
        self.output(json.dumps({"cycles": cycles, "devices": len(rows)}, ensure_ascii=False))

    def do_analyze(self, arg: str) -> None:
        """analyze [status.json] — genera inteligencia local desde un status JSON."""
        path = Path(arg.strip()) if arg.strip() else self.root / "data" / "cloud_state.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            status = payload.get("status") if isinstance(payload, dict) else None
            if not isinstance(status, dict):
                status = {"devices": payload.get("devices", []) if isinstance(payload, dict) else []}
            result = build_product(status)
            self.output(json.dumps(result["summary"], ensure_ascii=False))
        except Exception as exc:
            self.output(f"ERROR: {exc}")

    def do_export(self, arg: str) -> None:
        """export <path> — exporta el roadmap JSON a una ruta local."""
        args = shlex.split(arg)
        if len(args) != 1:
            self.output("uso: export <path>")
            return
        data = roadmap_tooling.load_roadmap()
        if not data:
            self.output("ERROR: roadmap no disponible")
            return
        target = Path(args[0]).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.output(str(target))

    def do_status(self, _arg: str) -> None:
        """status — muestra la ruta de trabajo y modo local."""
        self.output(json.dumps({"root": str(self.root), "mode": "local"}, ensure_ascii=False))

    def do_exit(self, _arg: str) -> bool:
        """exit — cierra la shell."""
        return True

    do_quit = do_exit

    def do_EOF(self, _arg: str) -> bool:
        self.output("")
        return True

    def emptyline(self) -> bool:
        return False
