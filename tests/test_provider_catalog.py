"""Test-verdad del catálogo de conectores UEM (lucidfence.saas.providers).

El wizard pide credenciales POR UEM según PROVIDER_CATALOG. Este módulo ancla
ese catálogo al contrato REAL de cada adapter:

  (a) cada `key` de los fields de un UEM es un kwarg que su constructor
      acepta de verdad (inspect.signature + instanciación offline);
  (b) todo field `type: "secret"` está en _SECRET_KEYS y mask_provider no lo
      re-emite jamás (y sí lo reconoce como "configured");
  (c) el shape de catalog() es estable: name/label/min_permission/fields
      ricos + field_keys plano para consumidores legacy.

Offline: no requiere credenciales ni red (los __init__ solo asignan).

Run via the runner:  python3 tests/run_tests.py
Run directly:        python3 tests/test_provider_catalog.py
"""
import inspect
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from lucidfence.core.adapters import ADAPTER_REGISTRY
from lucidfence.saas.providers import (
    PROVIDER_CATALOG,
    _SECRET_KEYS,
    catalog,
    mask_provider,
)

FIELD_TYPES = {"text", "secret", "url"}


def _accepted_kwargs(cls) -> tuple[set, bool]:
    """(nombres de kwargs del __init__, acepta **kwargs arbitrarios)."""
    sig = inspect.signature(cls.__init__)
    names = set()
    var_kw = False
    for p in sig.parameters.values():
        if p.name == "self":
            continue
        if p.kind is inspect.Parameter.VAR_KEYWORD:
            var_kw = True
        elif p.kind is not inspect.Parameter.VAR_POSITIONAL:
            names.add(p.name)
    return names, var_kw


def test_field_keys_match_adapter_contract():
    """(a) Cada key del catálogo es un kwarg real del adapter de ese UEM.

    Si un adapter cambia de credenciales, este test cae: el catálogo no puede
    prometer campos que el adapter no consume (era el bug: Jamf sin base_url,
    Fleet con api_key+endpoint, Workspace ONE con api_key+org_id).
    """
    for name, meta in PROVIDER_CATALOG.items():
        assert name in ADAPTER_REGISTRY, f"{name}: en catálogo pero sin adapter registrado"
        cls = ADAPTER_REGISTRY[name]
        accepted, var_kw = _accepted_kwargs(cls)
        keys = [f["key"] for f in meta["fields"]]
        assert len(keys) == len(set(keys)), f"{name}: keys duplicadas en fields"
        for key in keys:
            assert var_kw or key in accepted, (
                f"{name}: el campo {key!r} del catálogo no es un kwarg de "
                f"{cls.__name__}.__init__ (acepta: {sorted(accepted)})")
        # Prueba de fuego: construir el adapter con exactamente esos kwargs
        # (offline; los __init__ solo asignan). org_id/endpoint_template van
        # vacíos porque el server los pasa siempre (Applivery los exige).
        kwargs = {k: "x" for k in keys}
        kwargs.setdefault("org_id", "")
        kwargs.setdefault("endpoint_template", "")
        adapter = cls(**kwargs)
        assert adapter is not None, f"{name}: no se pudo construir con sus fields"
    print(f"  PASS field keys == contrato del adapter ({len(PROVIDER_CATALOG)} UEMs)")


def test_platform_schemas_are_the_real_ones():
    """Esquemas concretos que el propietario fijó (la verdad de cada API)."""
    keys = {n: [f["key"] for f in m["fields"]] for n, m in PROVIDER_CATALOG.items()}
    assert keys["applivery"] == ["api_key"], keys["applivery"]
    assert keys["intune"] == ["tenant_id", "client_id", "client_secret"], keys["intune"]
    # Sin URL no hay Jamf: base_url obligatoria en el esquema.
    assert keys["jamf"] == ["base_url", "client_id", "client_secret"], keys["jamf"]
    assert keys["fleet"] == ["base_url", "api_token"], keys["fleet"]
    assert keys["workspace_one"] == ["base_url", "tenant_code", "username", "password"], \
        keys["workspace_one"]
    assert keys["chromeos"] == ["client_id", "client_secret", "refresh_token", "customer_id"], \
        keys["chromeos"]
    assert keys["windows_conformidad"] == ["tenant_id", "client_id", "client_secret"], \
        keys["windows_conformidad"]
    assert keys["simulation"] == [], keys["simulation"]
    # customer_id es el único opcional (default my_customer en el adapter).
    optionals = {(n, f["key"]) for n, m in PROVIDER_CATALOG.items()
                 for f in m["fields"] if f.get("optional")}
    assert optionals == {("chromeos", "customer_id")}, optionals
    print("  PASS esquemas por UEM = contrato fijado (8 plataformas)")


def test_secret_fields_are_masked():
    """(b) Todo type=secret está en _SECRET_KEYS y mask_provider no lo devuelve."""
    secret_keys = [(n, f["key"]) for n, m in PROVIDER_CATALOG.items()
                   for f in m["fields"] if f["type"] == "secret"]
    assert secret_keys, "el catálogo debe declarar secretos"
    for name, key in secret_keys:
        assert key in _SECRET_KEYS, f"{name}.{key} es type=secret pero no está en _SECRET_KEYS"
        masked = mask_provider({"name": name, key: "sk-super-secreta"})
        assert key not in masked, f"{name}: mask_provider re-emite el secreto {key!r}"
        assert masked.get("configured") is True, \
            f"{name}: un {key!r} presente debe marcar configured=True"
    # El caso de la fuga original: Fleet guardado con api_token.
    fleet = mask_provider({"name": "fleet", "base_url": "https://fleet.x", "api_token": "tok"})
    assert "api_token" not in fleet and fleet["base_url"] == "https://fleet.x"
    print(f"  PASS {len(secret_keys)} campos secret enmascarados (_SECRET_KEYS)")


def test_catalog_shape_stable():
    """(c) catalog(): name+label+min_permission+fields ricos+field_keys plano."""
    cat = catalog()
    assert isinstance(cat, list) and len(cat) == len(PROVIDER_CATALOG)
    for entry in cat:
        assert entry["name"] in PROVIDER_CATALOG
        assert isinstance(entry["label"], str) and entry["label"]
        assert isinstance(entry["min_permission"], str) and entry["min_permission"], \
            f"{entry['name']}: min_permission vacío (la banda del wizard lo pinta)"
        assert isinstance(entry["fields"], list)
        for f in entry["fields"]:
            for req in ("key", "label", "type", "help"):
                assert isinstance(f.get(req), str) and f[req], \
                    f"{entry['name']}: field {f.get('key')!r} sin {req!r}"
            assert f["type"] in FIELD_TYPES, f"{entry['name']}.{f['key']}: type {f['type']!r}"
            assert "placeholder" in f, f"{entry['name']}.{f['key']}: sin placeholder"
        # field_keys: la vista plana para consumidores que solo quieren keys.
        assert entry["field_keys"] == [f["key"] for f in entry["fields"]]
    print(f"  PASS catalog() shape estable ({len(cat)} entradas)")


if __name__ == "__main__":
    failed = 0
    for fn in (test_field_keys_match_adapter_contract,
               test_platform_schemas_are_the_real_ones,
               test_secret_fields_are_masked,
               test_catalog_shape_stable):
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {fn.__name__}: {exc}")
    print(f"\n=== provider-catalog: {4 - failed} passed, {failed} failed ===")
    sys.exit(1 if failed else 0)
