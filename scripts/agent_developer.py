#!/usr/bin/env python3
"""
Agente Desarrollador — Implementa issues reales, escribe tests, abre PRs.
A diferencia de los agentes de monitoreo/QA, este AGENTE DE DESARROLLO
implementa código en el repo y abre PRs con cambios reales.

Hoy: implementar issue #310 (gap ruteo declarativo en engine + catálogo + tests).
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

REPO = Path("/Users/adri/lucidfence")
PY = "/Users/adri/lucidfence/.venv/bin/python"
ISSUE_NUMBER = 310
BRANCH_NAME = f"dev/issue-{ISSUE_NUMBER}-ddm-engine-gate"
GIT_USER = "Agente-Desarrollo"
GIT_EMAIL = "desarrollo@lucidfence.local"


def run(cmd: list[str], timeout: int = 60, cwd: Path | None = None) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd or REPO)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return f"TIMEOUT: {' '.join(cmd)}"
    except Exception as e:
        return f"ERROR: {e}"


def log(msg: str) -> None:
    print(f"[DESARROLLO] {msg}")


def claim_issue() -> bool:
    """Clamar el issue en GitHub antes de trabajar."""
    log(f"Clamando issue #{ISSUE_NUMBER}...")
    out = run(["gh", "issue", "edit", str(ISSUE_NUMBER), "--add-label", "dev:implementing"])
    if "error" in out.lower():
        log(f"  WARNING: no se pudo añadir label: {out[:100]}")
    # Asignar a sí mismo
    out = run(["gh", "issue", "edit", str(ISSUE_NUMBER), "--add-assignee", GIT_EMAIL])
    log(f"  Issue #{ISSUE_NUMBER} asignado a {GIT_EMAIL}")
    return True


def create_branch() -> bool:
    """Crear rama de trabajo en worktree (según AGENTS.md)."""
    log(f"Creando worktree en {REPO.parent / 'geofence-uem-dev-issue-310'}...")
    
    wt_dir = REPO.parent / "geofence-uem-dev-issue-310"
    
    # Remover worktree previo si existe
    if wt_dir.exists():
        run(["git", "worktree", "remove", str(wt_dir), "--force"])
    
    # Crear worktree
    out = run(["git", "worktree", "add", str(wt_dir), "-b", BRANCH_NAME, "origin/main"])
    if "fatal" in out.lower() or "error" in out.lower():
        log(f"  ERROR creando worktree: {out[:200]}")
        return False
    
    log(f"  Worktree creado en {wt_dir}")
    
    # Configurar identidad del worktree (NO --local, usar --worktree)
    run(["git", "config", "--worktree", "user.name", GIT_USER], cwd=wt_dir)
    run(["git", "config", "--worktree", "user.email", GIT_EMAIL], cwd=wt_dir)
    
    # Verificar identidad
    email = run(["git", "config", "user.email"], cwd=wt_dir).strip()
    if email != GIT_EMAIL:
        log(f"  ERROR: identidad mal configurada: {email}")
        return False
    
    log(f"  Identidad configurada: {email}")
    return True


def implement_ddm_gate_in_engine(wt_dir: Path) -> bool:
    """Implementar el gate declarativo en engine.run_command."""
    log("Implementando gate declarativo en engine.py...")
    
    engine_path = wt_dir / "lucidfence" / "core" / "engine.py"
    
    # Leer engine actual
    engine_content = engine_path.read_text()
    
    # Buscar el punto de inserción: después del cooldown check, antes de _execute_action
    # Necesitamos añadir la consulta a declarative_path_for
    
    # Imports necesarios: añadir import a declarative
    if "from lucidfence.core.declarative import" not in engine_content:
        # Añadir import después de los imports existentes
        import_line = "from lucidfence.core.declarative import declarative_path_for  # noqa: E402\n"
        # Buscar última línea de importa
        import_end = 0
        for i, line in enumerate(engine_content.splitlines()):
            if line.startswith("from ") or line.startswith("import "):
                import_end = i + 1
            elif import_end > 0 and line.strip() and not line.startswith("#"):
                break
        
        lines = engine_content.splitlines(keepends=True)
        lines.insert(import_end, import_line)
        engine_content = "".join(lines)
        log("  Añadido import declarative_path_for")
    
    # Ahora modificar run_command para consultar DDM
    # El patrón: después del cooldown check, antes de res = self._execute_action(...)
    # añadir: consulta a DDM si el action es declarativo-compatible
    
    old_pattern = "        res = self._execute_action(dev, action, params)\n"
    new_block = """        # Gate declarativo (issue #89): si el device y adapter soportan DDM,
        # ruteamos declarative en vez de imperativo.
        ddm_enforcement = None
        if action in ("apply_ddm", "wipe", "lock", "unlock", "rotate_passcode",
                       "apply_profile", "enforce_policy"):
            ddm_enforcement = declarative_path_for(
                dev,
                supports_ddm=bool(getattr(self, "supports_ddm", False)),
            )
            if ddm_enforcement == "declarative":
                # Delegamos al path declarativo del adapter
                res = self._execute_action(dev, "apply_ddm", params)
                res["enforcement"] = "declarative"
                res["ts"] = now_iso()
                res["fence_id"] = dev.inside_fence
                res["trigger"] = "operator"
                res["policy_name"] = "comando manual (declarativo)"
                res["operator"] = operator
                res["manual"] = True
                self.store.log_action(res)
                # Readback declarativo
                readback = res.get("device_state")
                if res.get("ok") and not self.dry_run and isinstance(readback, dict):
                    target = self.store.get(dev.device_id) or dev
                    merged = False
                    for key, value in readback.items():
                        if value is None or key == "device_id" or not hasattr(target, key):
                            continue
                        setattr(target, key, value)
                        merged = True
                    if merged:
                        self.store.upsert(target)
                effective = bool(res.get("dry_run") or res.get("ok") or res.get("delegated"))
                if action in self.DESTRUCTIVE_ACTIONS and effective:
                    self.store.record_action_at(dev.device_id, action, now)
                return res
            elif ddm_enforcement == "imperative":
                # Device no es declarative-eligible, continuamos imperativo
                pass
            # unknown: continuamos imperativo (no inferimos)
        
        res = self._execute_action(dev, action, params)
"""
    
    if old_pattern in engine_content:
        engine_content = engine_content.replace(old_pattern, new_block)
        engine_path.write_text(engine_content)
        log("  Gate declarativo añadido a engine.run_command")
        return True
    else:
        log("  ERROR: patrón de inserción no encontrado en engine.py")
        return False


def fix_provider_catalog(wt_dir: Path) -> bool:
    """Añadir estructura declarative al PROVIDER_CATALOG."""
    log("Añadiendo estructura declarative al PROVIDER_CATALOG...")
    
    providers_path = wt_dir / "lucidfence" / "saas" / "providers.py"
    content = providers_path.read_text()
    
    # Añadir campos declarative a cada provider
    old_catalog = """PROVIDER_CATALOG: dict[str, dict] = {
    "applivery": {"label": "Applivery", "fields": ["api_key", "org_id"]},
    "intune": {"label": "Microsoft Intune", "fields": ["tenant_id", "client_id", "client_secret"]},
    "jamf": {"label": "Jamf", "fields": ["client_id", "client_secret"]},
    "fleet": {"label": "FleetDM", "fields": ["api_key", "endpoint"]},
    "workspace_one": {"label": "Workspace ONE", "fields": ["api_key", "org_id"]},
    "chromeos": {"label": "ChromeOS", "fields": ["client_id", "client_secret", "refresh_token"]},
    "windows_conformidad": {"label": "Windows (conformidad)", "fields": ["api_key", "org_id"]},
    "simulation": {"label": "Simulación (demo)", "fields": []},
}"""
    
    new_catalog = """PROVIDER_CATALOG: dict[str, dict] = {
    "applivery": {"label": "Applivery", "fields": ["api_key", "org_id"], "declarative": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": False}},
    "intune": {"label": "Microsoft Intune", "fields": ["tenant_id", "client_id", "client_secret"], "declarative": {"supports_ddm": False, "supports_dsc": True, "supports_amapi_policy": True}},
    "jamf": {"label": "Jamf", "fields": ["client_id", "client_secret"], "declarative": {"supports_ddm": True, "supports_dsc": False, "supports_amapi_policy": False}},
    "fleet": {"label": "FleetDM", "fields": ["api_key", "endpoint"], "declarative": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": False}},
    "workspace_one": {"label": "Workspace ONE", "fields": ["api_key", "org_id"], "declarative": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": True}},
    "chromeos": {"label": "ChromeOS", "fields": ["client_id", "client_secret", "refresh_token"], "declarative": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": False}},
    "windows_conformidad": {"label": "Windows (conformidad)", "fields": ["api_key", "org_id"], "declarative": {"supports_ddm": False, "supports_dsc": True, "supports_amapi_policy": False}},
    "simulation": {"label": "Simulación (demo)", "fields": [], "declarative": {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": False}},
}"""
    
    if old_catalog in content:
        content = content.replace(old_catalog, new_catalog)
        
        # Añadir declarative a la función catalog()
        old_catalog_fn = '''        {"name": name, "label": meta["label"], "fields": meta["fields"]}
        for name, meta in PROVIDER_CATALOG.items()'''
        
        new_catalog_fn = '''        {"name": name, "label": meta["label"], "fields": meta["fields"],
         "declarative": meta.get("declarative", {"supports_ddm": False, "supports_dsc": False, "supports_amapi_policy": False})}
        for name, meta in PROVIDER_CATALOG.items()'''
        
        if new_catalog_fn in content:
            log("  ERROR: ya existe la versión con declarative (¿ya modificado?)")
            return False
        
        content = content.replace(old_catalog_fn, new_catalog_fn)
        providers_path.write_text(content)
        log("  PROVIDER_CATALOG actualizado con flags declarative")
        return True
    else:
        log("  ERROR: patrón de PROVIDER_CATALOG no encontrado")
        return False


def create_test_89(wt_dir: Path) -> bool:
    """Crear tests/test_89_declarative_routing.py con los 8 tests."""
    log("Creando tests/test_89_declarative_routing.py...")
    
    test_path = wt_dir / "tests" / "test_89_declarative_routing.py"
    
    test_content = '''"""
Tests para el gate declarativo en engine.run_command (issue #89).

Estos tests verifican que el engine rutea correctamente entre paths
declarativos e imperativos basándose en el management_mode del device
y las capacidades del adapter.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from lucidfence.core.engine import Engine, DeviceState, VALID_ACTIONS
from lucidfence.core.declarative import declarative_path_for, MANAGEMENT_MODES
from lucidfence.core.store import StateStore


# Helpers
def make_device(platform="ios", os_version="15.0", management_mode="mdm",
                ownership="company", device_id="test-device-1",
                inside_fence=True, policy_id=None):
    """Crear un DeviceState para pruebas."""
    kwargs = {
        "device_id": device_id,
        "platform": platform,
        "os_version": os_version,
        "management_mode": management_mode,
        "ownership": ownership,
        "inside_fence": inside_fence,
    }
    if policy_id:
        kwargs["policy_id"] = policy_id
    return DeviceState(**kwargs)


def make_engine(store=None, supports_ddm=False):
    """Crear un Engine para pruebas."""
    if store is None:
        import tempfile
        d = tempfile.mkdtemp()
        store = StateStore(Path(d))
    engine = Engine(store=store)
    engine.supports_ddm = supports_ddm
    return engine


# ── Tests del gate declarative_path_for ─────────────────────────────

class TestDeclarativePathFor:
    """Tests para declarative_path_for (gate de ruteo declarativo)."""
    
    def test_unknown_when_no_adapter_supports_declarative(self):
        """Si el adapter no soporta ningún canal declarativo, devuelve unknown."""
        dev = make_device()
        assert declarative_path_for(dev) == "unknown"
        assert declarative_path_for(dev, supports_ddm=False, supports_dsc=False,
                                     supports_amapi_policy=False) == "unknown"
    
    def test_unknown_when_management_mode_missing(self):
        """Si no hay management_mode, devuelve unknown (no inferimos)."""
        dev = make_device(management_mode=None)
        assert declarative_path_for(dev, supports_ddm=True) == "unknown"
        
        dev2 = make_device(management_mode="")
        assert declarative_path_for(dev2, supports_ddm=True) == "unknown"
    
    def test_unknown_when_management_mode_not_recognized(self):
        """Si el management_mode no está en la lista, devuelve unknown."""
        dev = make_device(management_mode="custom_mode")
        assert declarative_path_for(dev, supports_ddm=True) == "unknown"
    
    def test_declarative_for_ddm_fully_managed(self):
        """DDM + fully_managed -> declarative."""
        dev = make_device(management_mode="fully_managed")
        assert declarative_path_for(dev, supports_ddm=True) == "declarative"
    
    def test_declarative_for_ddm_mdm(self):
        """DDM + mdm -> declarative."""
        dev = make_device(management_mode="mdm")
        assert declarative_path_for(dev, supports_ddm=True) == "declarative"
    
    def test_declarative_for_ddm_configurator(self):
        """DDM + configurator -> declarative."""
        dev = make_device(management_mode="configurator")
        assert declarative_path_for(dev, supports_ddm=True) == "declarative"
    
    def test_imperative_for_byod_with_ddm(self):
        """DDM + employee_owned (BYOD) -> imperative."""
        dev = make_device(management_mode="mdm", ownership="employee_owned")
        assert declarative_path_for(dev, supports_ddm=True) == "imperative"
    
    def test_declarative_for_amapi_device_owner(self):
        """AMAPI + device_owner -> declarative."""
        dev = make_device(management_mode="device_owner")
        assert declarative_path_for(dev, supports_amapi_policy=True) == "declarative"
    
    def test_declarative_for_amapi_profile_owner(self):
        """AMAPI + profile_owner -> declarative."""
        dev = make_device(management_mode="profile_owner")
        assert declarative_path_for(dev, supports_amapi_policy=True) == "declarative"


# ── Tests de integración con engine.run_command ────────────────────

class TestEngineRoutingDeclarative:
    """Tests que verifican que engine.run_command rutea declarative cuando corresponde."""
    
    def test_engine_routes_ddm_declaratively_and_skips_imperative(self, tmp_path):
        """Cuando el device es DDM-eligible, run_command delega al path declarativo."""
        store = StateStore(tmp_path)
        engine = Engine(store=store)
        engine.supports_ddm = True
        
        dev = make_device(management_mode="fully_managed", device_id="ddm-device")
        
        result = engine.run_command(dev, "wipe")
        
        # El resultado debe tener enforcement="declarative"
        assert result.get("enforcement") == "declarative", \
            f"Esperado enforcement='declarative', got {result.get('enforcement')}"
    
    def test_engine_routes_wipe_declaratively_for_ddm_device(self, tmp_path):
        """Wipe en device DDM-eligible rutea declarative."""
        store = StateStore(tmp_path)
        engine = Engine(store=store)
        engine.supports_ddm = True
        
        dev = make_device(management_mode="mdm", device_id="ddm-wipe-device")
        
        result = engine.run_command(dev, "wipe")
        
        assert result.get("enforcement") == "declarative", \
            f"Esperado enforcement='declarative' para wipe DDM, got {result.get('enforcement')}"
    
    def test_engine_skips_declarative_for_non_ddm_device(self, tmp_path):
        """Device sin management_mode 적격한 -> rutea imperativo."""
        store = StateStore(tmp_path)
        engine = Engine(store=store)
        engine.supports_ddm = True
        
        dev = make_device(management_mode=None, device_id="no-mode-device")
        
        result = engine.run_command(dev, "wipe")
        
        # Sin management_mode, no rutea declarative
        assert result.get("enforcement") != "declarative", \
            "No debería rutear declarative para device sin management_mode"
    
    def test_engine_no_declarative_without_adapter_support(self, tmp_path):
        """Si el adapter no soporta DDM, no rutea declarative."""
        store = StateStore(tmp_path)
        engine = Engine(store=store)
        # supports_ddm = False (valor por defecto)
        
        dev = make_device(management_mode="fully_managed", device_id="no-ddm-device")
        
        result = engine.run_command(dev, "wipe")
        
        assert result.get("enforcement") != "declarative", \
            "No debería rutear declarative si el adapter no soporta DDM"


class TestProviderCatalogDeclarative:
    """Tests para PROVIDER_CATALOG con estructura declarative."""
    
    def test_provider_catalog_reflects_declarative_flags(self):
        """El catálogo debe espejar los flags declarative de cada provider."""
        from lucidfence.saas.providers import PROVIDER_CATALOG
        
        # Jamf soporta DDM (Apple)
        assert "declarative" in PROVIDER_CATALOG["jamf"], \
            "PROVIDER_CATALOG['jamf'] debe tener clave 'declarative'"
        assert PROVIDER_CATALOG["jamf"]["declarative"]["supports_ddm"] is True
        
        # Intune soporta DSC y AMAPI
        assert "declarative" in PROVIDER_CATALOG["intune"]
        assert PROVIDER_CATALOG["intune"]["declarative"]["supports_dsc"] is True
        assert PROVIDER_CATALOG["intune"]["declarative"]["supports_amapi_policy"] is True
        
        # Simulation no soporta nada declarativo
        assert PROVIDER_CATALOG["simulation"]["declarative"]["supports_ddm"] is False
        assert PROVIDER_CATALOG["simulation"]["declarative"]["supports_dsc"] is False
'''
    
    test_path.write_text(test_content)
    log(f"  Tests creados en {test_path}")
    return True


def run_tests(wt_dir: Path) -> bool:
    """Ejecutar tests de issue #310."""
    log("Ejecutando tests de issue #310...")
    
    # Ejecutar solo los tests de issue #89  
    out = run([
        PY, "-m", "pytest",
        "tests/test_89_declarative_routing.py",
        "-v", "--tb=short", "-x"
    ], cwd=wt_dir, timeout=120)
    
    log(f"Resultado tests:\n{out[:500]}")
    
    # Verificar que no hay FAILURES
    if "FAILED" in out or "ERROR" in out:
        log("  FAIL: hay tests fallando")
        return False
    
    if "passed" in out.lower():
        log("  OK: tests pasando")
        return True
    
    log(f"  UNKNOWN: resultado inesperado")
    return False


def commit_and_push(wt_dir: Path) -> str | None:
    """Hacer commit y push de la rama."""
    log("Haciendo commit...")
    
    # Stage todos los cambios
    run(["git", "add", "-A"], cwd=wt_dir)
    
    # Verificar qué se va a commitear
    status = run(["git", "status", "--short"], cwd=wt_dir).strip()
    if not status:
        log("  No hay cambios para commitear")
        return None
    
    log(f"  Changes to commit:\n{status}")
    
    # Commit
    commit_msg = f"""fix(engine): implementar gate ruteo declarativo (issue #310)

- Añadir consulta a declarative_path_for en engine.run_command
- Ruteo a path declarativo cuando device es DDM-eligible
- Añadir estructura declarative al PROVIDER_CATALOG (jamf:DDM, intune:DSC+AMAPI)
- Crear tests/test_89_declarative_routing.py (8 tests)

Closes #310

Co-Authored-By: Agente-Desarrollo <desarrollo@lucidfence.local>"""
    
    out = run(["git", "commit", "-m", commit_msg], cwd=wt_dir, timeout=30)
    if "error" in out.lower() or "nothing to commit" in out.lower():
        log(f"  ERROR commitando: {out[:200]}")
        return None
    
    log("  Commit realizado")
    
    # Push
    log("Push a origin...")
    out = run(["git", "push", "-u", "origin", BRANCH_NAME], cwd=wt_dir, timeout=60)
    if "error" in out.lower():
        log(f"  ERROR pushando: {out[:200]}")
        return None
    
    log("  Push completado")
    
    # Crear PR
    log("Creando PR...")
    cmd = [
        "gh", "pr", "create",
        "--title", f"fix(engine): implementar gate ruteo declarativo (issue #310)",
        "--body", f"""fix(engine): implementar gate ruteo declarativo (issue #310)

Implementa el gate ruteo declarativo en `engine.run_command` (issue #310 / #89).

### Cambios

- **engine.py**: `run_command` ahora consulta `declarative_path_for` y rutea a path declarativo cuando el device es DDM-eligible
- **providers.py**: `PROVIDER_CATALOG` ahora incluye estructura `declarative` con flags `supports_ddm`/`supports_dsc`/`supports_amapi_policy`
- **tests/test_89_declarative_routing.py**: 8 tests para el gate declarativo

### Testing

```
{COMMAND}
```

`{RESULT}`

### Resuena

- Closes #310

Co-Authored-By: Agente-Desarrollo <desarrollo@lucidfence.local>""",
        "--base", "main",
    ]
    out = run(cmd, cwd=REPO, timeout=30)
    
    # Extraer URL del PR
    import re
    match = re.search(r"https://github.com/adrimg3196/lucidfence/pull/(\d+)", out)
    if match:
        pr_url = f"https://github.com/adrimg3196/lucidfence/pull/{match.group(1)}"
        log(f"  PR creado: {pr_url}")
        return pr_url
    
    log(f"  WARNING: no se pudo extraer URL del PR: {out[:200]}")
    return None


def main():
    log("=" * 60)
    log("AGENTE DESARROLLADOR — Implementando issue #310")
    log("=" * 60)
    
    # 1. Claim del issue
    claim_issue()
    
    # 2. Crear worktree
    if not create_branch():
        log("FATAL: no se pudo crear worktree")
        return 1
    
    wt_dir = REPO.parent / "geofence-uem-dev-issue-310"
    
    # 3. Implementar cambios
    if not implement_ddm_gate_in_engine(wt_dir):
        log("FATAL: falló implementación engine")
        return 1
    
    if not fix_provider_catalog(wt_dir):
        log("FATAL: falló fix provider catalog")
        return 1
    
    if not create_test_89(wt_dir):
        log("FATAL: falló creación de tests")
        return 1
    
    # 4. Ejecutar tests
    if not run_tests(wt_dir):
        log("FATAL: tests fallando")
        return 1
    
    # 5. Commit + push + PR
    pr_url = commit_and_push(wt_dir)
    
    log("=" * 60)
    if pr_url:
        log(f"ÉXITO: PR creado → {pr_url}")
        log("=" * 60)
        return 0
    else:
        log("Fracaso: no se pudo crear PR")
        return 1


if __name__ == "__main__":
    sys.exit(main())
