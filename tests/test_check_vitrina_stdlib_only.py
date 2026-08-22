"""Regresion: el checker de la vitrina corre SIN dependencias de terceros.

Fallo real que cierra este test (encontrado 2026-08-22 por el loop DevOps):
`nightly-health-check.yml` ejecuta `python3 scripts/check_vitrina.py` sin
`pip install` — es un check de reachability, no necesita el producto entero.
Pero el checker importaba `PUBLISHED_REQUIRED_KEYS` de
`lucidfence.core.cloud_publisher`, que arrastra
cloud_publisher -> core.engine -> core.actions -> core.adapters -> applivery,
y applivery hace `import requests` a nivel de modulo.

Consecuencia medida en produccion: 10 runs nocturnos consecutivos en rojo
(2026-08-13 .. 2026-08-22) con `ModuleNotFoundError: No module named
'requests'`, mientras la vitrina estaba viva y sana todo el tiempo. Una alarma
en rojo permanente no puede alertar: no distingue "vitrina caida" de "el
checker no arranca".

El test de contrato existente (test_single_source_cloud_state.py) comprobaba
que el workflow LLAMA al checker, no que el checker pueda EJECUTARSE en ese
entorno. Este cierra ese hueco: prohibe los modulos de terceros del proyecto y
exige que el checker siga arrancando.
"""
import os
import subprocess
import sys
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Terceros que el repo declara en requirements.txt (mas su cierre transitivo
# habitual). El runner de GitHub Actions no los tiene sin `pip install`.
_THIRD_PARTY = (
    "requests", "urllib3", "certifi", "idna", "charset_normalizer",
    "chardet", "cryptography", "jwt", "yaml", "dotenv", "playwright",
)

_HARNESS = textwrap.dedent(
    '''
    import runpy, sys
    BANNED = {banned!r}

    class _NoThirdParty:
        """Simula el runner limpio: cualquier tercero es ImportError."""
        def find_module(self, name, path=None):
            return self.find_spec(name, path)

        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in BANNED:
                raise ImportError(
                    "No module named %r (bloqueado por el test de regresion: "
                    "check_vitrina debe ser stdlib puro)" % name
                )
            return None

    sys.meta_path.insert(0, _NoThirdParty())
    # Purga lo ya importado por el interprete padre para que el bloqueo aplique.
    for _m in list(sys.modules):
        if _m.split(".")[0] in BANNED:
            del sys.modules[_m]

    sys.argv = [{script!r}, "--url-only"]
    try:
        runpy.run_path({script!r}, run_name="__main__")
    except SystemExit as exc:
        sys.exit(exc.code or 0)
    '''
)


def _run_without_third_party(script_rel):
    script = os.path.join(ROOT, script_rel)
    code = _HARNESS.format(banned=set(_THIRD_PARTY), script=script)
    env = dict(os.environ)
    # Sin PYTHONPATH heredado: el script debe resolver el paquete el solo.
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=60,
    )


def test_check_vitrina_arranca_sin_dependencias_de_terceros():
    """El nightly lo corre sin pip install: tiene que arrancar igual."""
    proc = _run_without_third_party(os.path.join("scripts", "check_vitrina.py"))
    assert proc.returncode == 0, (
        "check_vitrina.py no arranca sin terceros — nightly-health-check.yml "
        "lo ejecuta asi y quedaria en rojo permanente.\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    # --url-only no toca la red: la salida es la URL canonica.
    assert "raw.githubusercontent.com" in proc.stdout, proc.stdout
    assert "ModuleNotFoundError" not in proc.stderr, proc.stderr


def test_published_schema_es_una_hoja_sin_imports():
    """published_schema no puede volver a acoplarse al engine."""
    import ast

    path = os.path.join(ROOT, "lucidfence", "core", "published_schema.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    forbidden = [m for m in imported if m != "__future__"]
    assert not forbidden, (
        "published_schema.py debe ser una HOJA sin imports (es lo que permite "
        f"que check_vitrina sea stdlib puro); encontrados: {forbidden}"
    )


def test_el_contrato_sigue_siendo_uno_solo():
    """La hoja y el publisher exponen EL MISMO objeto, no una copia."""
    sys.path.insert(0, ROOT)
    from lucidfence.core.published_schema import PUBLISHED_REQUIRED_KEYS as leaf
    from lucidfence.core.cloud_publisher import PUBLISHED_REQUIRED_KEYS as pub

    assert leaf is pub, "el esquema se ha duplicado: vuelve a poder derivar"
    assert set(leaf) >= {"devices", "fences", "generated_at", "service"}
