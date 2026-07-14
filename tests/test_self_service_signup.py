"""Tests del flujo self-service determinista issue -> tenant -> vitrina.

Cubre el cambio de t_ada1c510:
- El parser del issue (scripts/parse_signup_issue.py) extrae tenant_id,
  fleet y fences del bloque delimitado, y rechaza issues sin el bloque.
- La validación de tenant_id (scripts/saas_api_op.py) solo acepta
  alfanumérico, guion y guion bajo (defensa anti path-traversal).
- El workflow .github/workflows/saas-signup.yml:
  * propaga ISSUE_NUMBER al step de commit (evita el commit "cloud: tenant
    desde signup (#)" sin número).
  * incluye un paso que regenera data/cloud_state.json con cloud_publisher.py
    en el MISMO run (SLA determinista, sin depender del cron engine-cron).

Son tests de lógica pura / estructura de YAML; no arrancan el server ni
GitHub Actions.
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None, f"no se pudo cargar {path}"
    assert spec.loader is not None, f"spec sin loader para {path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Parser del issue
# ---------------------------------------------------------------------------
def test_parse_block_extrae_campos():
    mod = _load(ROOT / "scripts" / "parse_signup_issue.py")
    body = (
        "Hola,\n"
        "<!-- lucidfence-signup -->\n"
        "tenant_id: empresa-xyz\n"
        'fleet: [{"id":"d1","name":"Camion 1","platform":"android",'
        '"lat":40.42,"lng":-3.70,"compliant":true,"department":"Reparto"}]\n'
        'fences: [{"id":"hq","name":"HQ","kind":"circle",'
        '"center":{"lat":40.42,"lng":-3.70},"radius_m":500}]\n'
        "<!-- /lucidfence-signup -->\n"
        "Gracias."
    )
    data = mod.parse_block(body)
    assert data["tenant_id"] == "empresa-xyz", data
    assert len(data["fleet"]) == 1
    assert data["fleet"][0]["name"] == "Camion 1"
    assert len(data["fences"]) == 1
    assert data["fences"][0]["id"] == "hq"


def test_parse_block_sin_bloque_lanza_ValueError():
    mod = _load(ROOT / "scripts" / "parse_signup_issue.py")
    try:
        mod.parse_block("issue normal sin nada")
        raise AssertionError("deberia haber lanzado ValueError")
    except ValueError:
        pass


def test_parse_block_json_invalido_lanza_ValueError():
    mod = _load(ROOT / "scripts" / "parse_signup_issue.py")
    # El parser solo valida JSON cuando el bracket [] coincide; un array mal
    # formado pero con corchetes debe lanzar ValueError al hacer json.loads.
    body = (
        "<!-- lucidfence-signup -->\n"
        "tenant_id: empresa-xyz\n"
        "fleet: [esto, no, es, json]\n"
        "<!-- /lucidfence-signup -->"
    )
    try:
        mod.parse_block(body)
        raise AssertionError("deberia haber lanzado ValueError por JSON roto")
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Validación de tenant_id (anti path-traversal)
# ---------------------------------------------------------------------------
def test_tenant_dir_rechaza_ids_invalidos():
    mod = _load(ROOT / "scripts" / "saas_api_op.py")
    for bad in ["a/b", "../x", "a;rm", "a b", ""]:
        try:
            mod._tenant_dir(bad)
            raise AssertionError("tenant_id invalido aceptado: %r" % bad)
        except ValueError:
            pass
    # ids validos no lanzan y la ruta apunta a <id>/data
    ok = mod._tenant_dir("empresa-xyz_1")
    assert ok.parent.name == "empresa-xyz_1", ok
    assert ok.name == "data", ok


# ---------------------------------------------------------------------------
# Estructura del workflow saas-signup.yml
# ---------------------------------------------------------------------------
def test_workflow_contiene_ISSUE_NUMBER_en_commit_y_regeneracion():
    wf = _read(ROOT / ".github" / "workflows" / "saas-signup.yml")
    # 1) El step de commit debe usar ISSUE_NUMBER (corrige el "cloud: ... (#)").
    assert 'git commit -m "cloud: tenant desde signup (#$ISSUE_NUMBER)"' in wf, \
        "el commit de tenant no propaga ISSUE_NUMBER"
    assert "ISSUE_NUMBER: ${{ github.event.issue.number }}" in wf, \
        "falta inyectar ISSUE_NUMBER en el step de commit"
    # 2) Debe regenerar cloud_state.json en el mismo run (determinista).
    assert "cloud_publisher.py" in wf, \
        "falta regenerar la vitrina con cloud_publisher.py"
    assert "data/cloud_state.json" in wf, \
        "falta commitear data/cloud_state.json en el mismo run"


def test_workflow_sin_depender_del_cron_para_publicar():
    wf = _read(ROOT / ".github" / "workflows" / "saas-signup.yml")
    # El nuevo paso de regeneracion no debe depender de engine-cron: la
    # publicacion ocurre dentro de saas-signup, no por disparo externo.
    assert "Regenerar vitrina" in wf
    # Si alguna vez se vuelve a depender del cron, debe ser explicito; aqui
    # verificamos que el paso corre inline (run: python cloud_publisher.py).
    idx_pub = wf.find("Regenerar vitrina")
    snippet = wf[idx_pub:idx_pub + 600]
    assert "python cloud_publisher.py" in snippet
    assert "workflow_dispatch" not in snippet or "engine-cron" not in wf.split("Regenerar vitrina")[1][:200], \
        "no debe delegar la publicacion en engine-cron"


def test_workflow_yaml_sintacticamente_valido():
    wf_path = ROOT / ".github" / "workflows" / "saas-signup.yml"
    try:
        import yaml  # type: ignore
    except Exception:
        # PyYAML no disponible: validacion minima por estructura.
        text = _read(wf_path)
        assert text.strip().startswith("name: saas-signup"), "YAML no empieza con name"
        assert "on:" in text and "jobs:" in text
        return
    with open(str(wf_path), encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    assert doc["name"] == "saas-signup"
    # PyYAML (YAML 1.1) interpreta la clave `on` como booleano True; GitHub
    # Actions (YAML 1.2) la trata como clave normal. Aceptamos ambos.
    on = doc.get("on", doc.get(True))
    assert on is not None, "falta la seccion 'on'"
    assert "issues" in on, "'on' debe dispararse por issues"
    jobs = doc.get("jobs", {})
    assert "create-tenant" in jobs
    steps = jobs["create-tenant"]["steps"]
    names = [s.get("name", "") for s in steps]
    assert any("Regenerar vitrina" in n for n in names), \
        "falta el step de regeneracion de vitrina"
    assert any("Commitear tenant" in n for n in names)
    # El nuevo step de regeneracion se ejecuta solo si se creo un tenant.
    regen = [s for s in steps if "Regenerar vitrina" in s.get("name", "")][0]
    assert "steps.parse.outputs.tenant_created" in regen.get("if", ""), \
        "el step de regeneracion debe estar condicionado a tenant creado"
