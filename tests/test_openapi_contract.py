"""Test that the OpenAPI spec matches the actual API routes served by the server."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
openapi_path = ROOT / "openapi.json"
saas_server_path = ROOT / "saas_server.py"


def test_openapi_bidirectional_contract():
    # 1. Parse openapi.json
    assert openapi_path.exists(), "openapi.json does not exist in the root of the repository!"

    with open(openapi_path, encoding="utf-8") as f:
        spec = json.load(f)

    assert "openapi" in spec, "openapi.json is missing the openapi version field"
    assert "paths" in spec, "openapi.json is missing the paths field"

    spec_endpoints = set()
    for path, methods in spec["paths"].items():
        for method in methods:
            spec_endpoints.add((path, method.upper()))

    # 2. Parse saas_server.py using AST
    with open(saas_server_path, encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Find _route and _product functions inside the tree
    route_func = None
    product_func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name == "_route":
                route_func = node
            elif node.name == "_product":
                product_func = node

    assert route_func is not None, "Could not find _route function in saas_server.py"
    assert product_func is not None, "Could not find _product function in saas_server.py"

    server_endpoints = set()

    # Helper to clean route to openapi format
    def clean_path(r: str) -> str:
        if r.startswith("/api"):
            r = r[4:]
        return r or "/"

    def get_methods_for_node(node: ast.AST) -> set[str]:
        methods = set()
        parent = getattr(node, "parent_test", None)
        if parent:
            for sub in ast.walk(parent):
                if isinstance(sub, ast.Compare):
                    if isinstance(sub.left, ast.Name) and sub.left.id == "method":
                        for op, comp in zip(sub.ops, sub.comparators):
                            if isinstance(op, ast.Eq) and isinstance(comp, ast.Constant):
                                methods.add(comp.value.upper())
                            elif isinstance(op, ast.In) and isinstance(comp, (ast.Tuple, ast.List, ast.Set)):
                                for el in comp.elts:
                                    if isinstance(el, ast.Constant):
                                        methods.add(el.value.upper())
        if not methods:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Compare):
                    if isinstance(sub.left, ast.Name) and sub.left.id == "method":
                        for op, comp in zip(sub.ops, sub.comparators):
                            if isinstance(op, ast.Eq) and isinstance(comp, ast.Constant):
                                methods.add(comp.value.upper())
        if not methods:
            methods.add("GET")
        return methods

    def expand_startswith_route(prefix: str, node: ast.AST) -> None:
        methods = get_methods_for_node(node)
        if prefix == "/api/auth/sso/":
            server_endpoints.add(("/auth/sso/{provider}/start", "GET"))
            server_endpoints.add(("/auth/sso/{provider}/callback", "GET"))
        elif prefix == "/api/soar/webhook/":
            server_endpoints.add(("/soar/webhook/{org_id}", "POST"))
        elif prefix == "/api/api-keys/":
            server_endpoints.add(("/api-keys/{id}", "DELETE"))
        elif prefix == "/api/company/tasks/":
            server_endpoints.add(("/company/tasks/{task_id}/approve", "POST"))
            server_endpoints.add(("/company/tasks/{task_id}/reject", "POST"))
        elif prefix == "/api/fences/":
            server_endpoints.add(("/fences/{id}", "DELETE"))
        elif prefix == "/api/routes/":
            server_endpoints.add(("/routes/{id}/delete", "POST"))
        elif prefix == "/api/workflows/":
            server_endpoints.add(("/workflows/{id}/delete", "POST"))
        elif prefix == "/api/orgs/":
            server_endpoints.add(("/orgs/{id}/switch", "POST"))
        elif prefix == "/api/devices/":
            server_endpoints.add(("/devices/{id}", "GET"))
            server_endpoints.add(("/devices/{id}/command", "POST"))
        elif prefix == "/api/incidents/":
            server_endpoints.add(("/incidents/{id}/transition", "POST"))
        elif prefix == "/api/alerts/":
            server_endpoints.add(("/alerts/{id}/delete", "POST"))

    # Walk all 'If' and comparison nodes in both functions
    def process_func(func: ast.FunctionDef) -> None:
        for node in ast.walk(func):
            if isinstance(node, ast.Compare):
                # Check for: route == "..."
                if isinstance(node.left, ast.Name) and node.left.id == "route":
                    for op, comp in zip(node.ops, node.comparators):
                        if isinstance(op, ast.Eq) and isinstance(comp, ast.Constant):
                            r = comp.value
                            if r.startswith("/api/"):
                                methods = get_methods_for_node(node)
                                for m in methods:
                                    server_endpoints.add((clean_path(r), m))
                        elif isinstance(op, ast.In):
                            if isinstance(comp, (ast.Tuple, ast.List, ast.Set)):
                                for el in comp.elts:
                                    if isinstance(el, ast.Constant):
                                        r = el.value
                                        if r.startswith("/api/"):
                                            methods = get_methods_for_node(node)
                                            for m in methods:
                                                server_endpoints.add((clean_path(r), m))
                # Check for: "..." == route
                elif isinstance(node.left, ast.Constant):
                    for op, comp in zip(node.ops, node.comparators):
                        if isinstance(op, ast.Eq) and isinstance(comp, ast.Name) and comp.id == "route":
                            r = node.left.value
                            if r.startswith("/api/"):
                                methods = get_methods_for_node(node)
                                for m in methods:
                                    server_endpoints.add((clean_path(r), m))

            elif isinstance(node, ast.Call):
                # Check for route.startswith(...)
                if isinstance(node.func, ast.Attribute) and node.func.attr == "startswith":
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "route":
                        if node.args and isinstance(node.args[0], ast.Constant):
                            prefix = node.args[0].value
                            if prefix.startswith("/api/"):
                                expand_startswith_route(prefix, node)

    # Pre-populate parent_test attributes on all AST nodes for backtracking
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While)):
            for child in ast.walk(node.test):
                child.parent_test = node.test  # type: ignore
        elif isinstance(node, ast.BoolOp):
            for value in node.values:
                for child in ast.walk(value):
                    child.parent_test = node  # type: ignore

    process_func(route_func)
    process_func(product_func)

    # Assert bidirectionality
    undocumented = server_endpoints - spec_endpoints
    extra_in_spec = spec_endpoints - server_endpoints

    # Let's filter out endpoints we do not want to document or are private/non-API (like /api/readyz, etc if any, but wait, we want to cover them all)
    # The requirement is: "La spec cubre todas las rutas /api/v2/* servidas hoy: método, path, params, cuerpo de request/response, códigos de error."
    # Let's see if we have undocumented or extra endpoints
    assert not undocumented, f"There are undocumented endpoints served by saas_server.py: {sorted(undocumented)}"
    assert not extra_in_spec, f"There are endpoints in openapi.json that are not served by saas_server.py: {sorted(extra_in_spec)}"
