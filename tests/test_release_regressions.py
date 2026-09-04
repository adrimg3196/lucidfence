import base64
import hashlib
import importlib.machinery
import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    name = "lucidfence_cli_regression_%s" % os.getpid()
    return importlib.machinery.SourceFileLoader(name, str(ROOT / "lucidfence" / "cli.py")).load_module()


def test_stop_refuses_unrelated_reused_pid():
    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("LUCIDFENCE_DATA_DIR")
        os.environ["LUCIDFENCE_DATA_DIR"] = tmp
        sleeper = subprocess.Popen(["sleep", "30"])
        try:
            (Path(tmp) / "lucidfence.pid").write_text(str(sleeper.pid))
            cli = _load_cli()
            result = cli.cmd_stop(SimpleNamespace(host="127.0.0.1", port=65530))
            assert result == 1
            assert sleeper.poll() is None
            assert not (Path(tmp) / "lucidfence.pid").exists()
        finally:
            if sleeper.poll() is None:
                sleeper.terminate()
                sleeper.wait(timeout=5)
            if old is None:
                os.environ.pop("LUCIDFENCE_DATA_DIR", None)
            else:
                os.environ["LUCIDFENCE_DATA_DIR"] = old


def test_failed_start_rolls_back_pid_and_child():
    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("LUCIDFENCE_DATA_DIR")
        os.environ["LUCIDFENCE_DATA_DIR"] = tmp
        try:
            cli = _load_cli()
            result = cli.cmd_start(SimpleNamespace(host="203.0.113.1", port=65529, open=False))
            assert result == 1
            assert not (Path(tmp) / "lucidfence.pid").exists()
        finally:
            if old is None:
                os.environ.pop("LUCIDFENCE_DATA_DIR", None)
            else:
                os.environ["LUCIDFENCE_DATA_DIR"] = old


def test_restart_does_not_start_when_stop_fails():
    cli = _load_cli()
    calls = []
    setattr(cli, "cmd_stop", lambda _args: 1)
    setattr(cli, "cmd_start", lambda _args: calls.append("start") or 0)
    result = cli.cmd_restart(SimpleNamespace())
    assert result == 1
    assert calls == []


def test_all_app_assets_are_root_absolute():
    html = (ROOT / "static" / "dashboard.html").read_text()
    js = (ROOT / "static" / "app.js").read_text()
    assert 'href="/static/' in html
    assert 'src="/static/' in html
    assert '"/static/vendor/offline-map.svg"' in js
    assert '"static/' not in html
    assert '"static/' not in js


def test_map_and_device_table_have_independent_filters():
    js = (ROOT / "static" / "app.js").read_text()
    assert "mapFilter" in js
    map_block = js[js.index("function initMap"):js.index("function renderDevices")]
    assert "App.devFilter" not in map_block


def test_offline_map_declares_real_web_mercator_projection():
    js = (ROOT / "static" / "app.js").read_text()
    svg = (ROOT / "static" / "vendor" / "offline-map.svg").read_text()
    assert "offline-iberia" not in js
    assert 'data-projection="EPSG:3857"' in svg


def test_map_views_use_unique_dom_ids():
    js = (ROOT / "static" / "app.js").read_text()
    assert 'id="map"' not in js
    assert 'id="overviewMap"' in js
    assert 'id="fleetMap"' in js
    assert 'initMap(devs, "overviewMap")' in js
    assert 'initMap(App.status.devices||[], "fleetMap")' in js


def test_demo_and_gateway_use_actual_bound_socket():
    import saas_server
    loopback = SimpleNamespace(server=SimpleNamespace(server_address=("127.0.0.1", 8765)), client_address=("127.0.0.1", 1234), headers={})
    exposed = SimpleNamespace(server=SimpleNamespace(server_address=("0.0.0.0", 8765)), client_address=("127.0.0.1", 1234), headers={})
    assert saas_server._bound_host(loopback) == "127.0.0.1"
    assert saas_server._gateway_allowed(loopback) is True
    assert saas_server._gateway_allowed(exposed) is False
    server = (ROOT / "saas_server.py").read_text()
    assert "bound_host = _bound_host(self)" in server


def test_quick_runner_uses_supported_python_and_hash_locked_venv():
    runner = (ROOT / "scripts" / "run.sh").read_text()
    assert "3, 11" in runner
    assert "-m venv" in runner
    assert "requirements.lock" in runner
    assert "--require-hashes" in runner
    assert 'exec "$VENV_PYTHON" saas_server.py' in runner
    assert "pip install requests" not in runner


def _load_script(script_name):
    name = "lucidfence_%s_%s" % (script_name.replace(".", "_"), os.getpid())
    return importlib.machinery.SourceFileLoader(name, str(ROOT / "scripts" / script_name)).load_module()


def _dsse_with_statement(statement):
    payload = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"payloadType": "application/vnd.in-toto+json", "payload": base64.b64encode(payload).decode("ascii"), "signatures": []}


def test_pypi_workflow_checks_provenance_after_building_artifact():
    workflow = (ROOT / ".github" / "workflows" / "publish-pypi.yml").read_text()
    build_idx = workflow.index("name: Build package")
    prov_idx = workflow.index("name: Generate SBOM and provenance for package")
    publish_idx = workflow.index("name: Publish to PyPI")
    assert build_idx < prov_idx < publish_idx
    provenance_block = workflow[prov_idx:publish_idx]
    assert "scripts/provenance_attest.py" in provenance_block
    assert "scripts/release_preflight.py" in provenance_block
    assert "artifact=\"$(find dist -maxdepth 1 -type f -name '*.tar.gz' -print -quit)\"" in provenance_block
    assert '--artifact "$artifact"' in provenance_block
    assert "--sbom build/provenance/sbom.cdx.json" in provenance_block
    assert "--dsse build/provenance/provenance.dsse.json" in provenance_block


ARTIFACT_VERSION = "1.6.1"


def test_provenance_verifier_with_key_works_without_site_packages():
    import shutil
    import sys
    py_bin = shutil.which("python3.11") or sys.executable
    fixture = ROOT / "docs" / "supply-chain" / "fixture"
    result = subprocess.run(
        [py_bin, "-S", str(ROOT / "scripts" / "verify_provenance.py"),
         "--artifact", str(fixture / f"lucidfence-{ARTIFACT_VERSION}.tar.gz"),
         "--sbom", str(fixture / "sbom.cdx.json"),
         "--dsse", str(fixture / "provenance.dsse.json"),
         "--key", str(fixture / "release_signing_demo.pub"),
         "--repo", str(ROOT)],
        cwd=str(ROOT), capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "VERIFY PROVENANCE: APTO" in result.stdout


def test_ci_python_job_fetches_history_for_provenance_fixture():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    python_job = workflow[workflow.index("  python:"):workflow.index("  verify-docs:")]

    assert "fetch-depth: 0" in python_job


def test_release_workflow_publishes_sbom_and_provenance_assets():
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    build_idx = workflow.index("name: Construir tarball versionado")
    prov_idx = workflow.index("name: Generar SBOM y procedencia offline")
    preflight_idx = workflow.index("name: Release preflight con artefacto, SBOM y procedencia")
    publish_idx = workflow.index("name: Crear GitHub Release con el asset")
    assert build_idx < prov_idx < preflight_idx < publish_idx
    assert "scripts/provenance_attest.py" in workflow[prov_idx:preflight_idx]
    assert '--artifact "dist/lucidfence-$VERSION.tar.gz"' in workflow[preflight_idx:publish_idx]
    assert "--sbom dist/sbom.cdx.json" in workflow[preflight_idx:publish_idx]
    assert "--dsse dist/provenance.dsse.json" in workflow[preflight_idx:publish_idx]
    release_block = workflow[publish_idx:]
    assert "dist/sbom.cdx.json" in release_block
    assert "dist/provenance.dsse.json" in release_block


def test_release_preflight_rejects_stale_sbom_not_bound_to_attestation():
    rp = _load_script("release_preflight.py")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifact = root / f"lucidfence-{ARTIFACT_VERSION}.tar.gz"
        sbom = root / "sbom.cdx.json"
        dsse = root / "provenance.dsse.json"
        artifact.write_bytes(b"artifact")
        sbom.write_text('{"bomFormat":"CycloneDX","specVersion":"1.5"}x', encoding="utf-8")
        statement = {
            "subject": [{"name": artifact.name, "digest": {"sha256": "ignored"}}],
            "predicate": {"sbom": {"sha256": "not-the-current-sbom"}},
        }
        dsse.write_text(json.dumps(_dsse_with_statement(statement)), encoding="utf-8")

        ok, detail = rp.check_prov_sbom_match(str(root), artifact=str(artifact), sbom=str(sbom), dsse=str(dsse))

        assert ok is False
        assert detail["expected"] == "not-the-current-sbom"


def test_release_preflight_rejects_artifact_version_mismatch():
    rp = _load_script("release_preflight.py")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text(f'[project]\nversion = "{ARTIFACT_VERSION}"\n', encoding="utf-8")
        artifact = root / f"lucidfence-9.9.9.tar.gz"
        dsse = root / "provenance.dsse.json"
        artifact.write_bytes(b"artifact")
        statement = {
            "subject": [{"name": artifact.name, "digest": {"sha256": "ignored"}}],
            "predicate": {"version": ARTIFACT_VERSION, "artifactVersion": "9.9.9", "versionConsistent": False},
        }
        dsse.write_text(json.dumps(_dsse_with_statement(statement)), encoding="utf-8")

        ok, detail = rp.check_prov_version_match(str(root), artifact=str(artifact), dsse=str(dsse))

        assert ok is False
        assert detail["versions"]["artifact"] == "9.9.9"
        assert detail["versionConsistent"] is False


def test_provenance_verifier_without_key_is_not_apto():
    vp = _load_script("verify_provenance.py")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text(f'[project]\nversion = "{ARTIFACT_VERSION}"\n', encoding="utf-8")
        artifact = root / f"lucidfence-{ARTIFACT_VERSION}.tar.gz"
        sbom = root / "sbom.cdx.json"
        dsse = root / "provenance.dsse.json"
        artifact.write_bytes(b"artifact")
        sbom.write_text('{"bomFormat":"CycloneDX","specVersion":"1.5"}', encoding="utf-8")
        artifact_sha = vp.sha256_bytes(artifact.read_bytes())
        sbom_sha = vp.sha256_bytes(sbom.read_bytes())
        statement = {
            "subject": [{"name": artifact.name, "digest": {"sha256": artifact_sha}}],
            "predicate": {
                "version": ARTIFACT_VERSION,
                "artifactVersion": ARTIFACT_VERSION,
                "versionConsistent": True,
                "sbom": {"sha256": sbom_sha},
                "invocation": {"configSource": {"commit": ""}},
                "metadata": {},
            },
        }
        dsse.write_text(json.dumps(_dsse_with_statement(statement)), encoding="utf-8")

        import shutil
        import sys
        py_bin = shutil.which("python3.11") or sys.executable
        result = subprocess.run(
            [py_bin, str(ROOT / "scripts" / "verify_provenance.py"),
             "--artifact", str(artifact), "--sbom", str(sbom), "--dsse", str(dsse),
             "--repo", str(root)],
            cwd=str(ROOT), capture_output=True, text=True,
        )

        assert result.returncode != 0
        assert "VERIFY PROVENANCE: FALLO" in result.stdout
        assert "signature_authenticated" in result.stdout


def test_dsse_signature_uses_pae_not_raw_payload():
    pa = _load_script("provenance_attest.py")
    payload = b'{"hello":"world"}'

    assert pa.dsse_pae("application/vnd.in-toto+json", payload) != payload
    assert pa.dsse_pae("application/vnd.in-toto+json", payload) == (
        b"DSSEv1 28 application/vnd.in-toto+json 17" + payload
    )


def test_provenance_verifier_rejects_absent_commit_even_when_signed():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

    vp = _load_script("verify_provenance.py")
    fixture = ROOT / "docs" / "supply-chain" / "fixture"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        key = Ed25519PrivateKey.generate()
        pub_raw = key.public_key().public_bytes_raw()
        private_key = tmp_path / "release.key"
        public_key = tmp_path / "release.pub"
        private_key.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
        public_key.write_bytes(key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
        dsse = tmp_path / "fake-commit.dsse.json"
        statement, _payload, env = vp.parse_dsse((fixture / "provenance.dsse.json").read_bytes())
        statement["predicate"]["invocation"]["configSource"]["commit"] = "0" * 40
        payload = vp.canonical_json(statement)
        env["payload"] = base64.b64encode(payload).decode("ascii")
        env["signatures"] = [{
            "keyid": hashlib.sha256(pub_raw).hexdigest()[:32],
            "sig": base64.b64encode(key.sign(vp.dsse_pae(vp.DSSE_PAYLOAD_TYPE, payload))).decode("ascii"),
        }]
        dsse.write_text(json.dumps(env), encoding="utf-8")

        results = vp.run(
            fixture / f"lucidfence-{ARTIFACT_VERSION}.tar.gz",
            fixture / "sbom.cdx.json",
            dsse,
            ROOT,
            public_key,
        )

    assert results["signature_authenticated"]["ok"] is True
    assert results["commit_linked"]["ok"] is False
    assert results["commit_linked"]["status"] == "unknown"


def test_release_preflight_requires_authenticated_provenance_when_releasing():
    rp = _load_script("release_preflight.py")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifact = root / f"lucidfence-{ARTIFACT_VERSION}.tar.gz"
        sbom = root / "sbom.cdx.json"
        dsse = root / "provenance.dsse.json"
        artifact.write_bytes(b"artifact")
        sbom.write_text('{"bomFormat":"CycloneDX","specVersion":"1.5"}', encoding="utf-8")
        statement = {
            "subject": [{"name": artifact.name, "digest": {"sha256": _load_script("verify_provenance.py").sha256_bytes(artifact.read_bytes())}}],
            "predicate": {
                "version": ARTIFACT_VERSION,
                "artifactVersion": ARTIFACT_VERSION,
                "versionConsistent": True,
                "sbom": {"sha256": _load_script("verify_provenance.py").sha256_bytes(sbom.read_bytes())},
                "invocation": {"configSource": {"commit": ""}},
                "metadata": {},
            },
        }
        dsse.write_text(json.dumps(_dsse_with_statement(statement)), encoding="utf-8")

        ok, detail = rp.check_prov_signature_authenticated(
            str(root), artifact=str(artifact), sbom=str(sbom), dsse=str(dsse), key=None
        )

    assert ok is False
    assert "--key" in detail["error"]


def test_release_workflow_signs_and_preflights_authenticated_provenance_at_release_commit():
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    assert 'git checkout --detach "${{ github.sha }}"' in workflow
    assert "openssl genpkey -algorithm Ed25519 -out dist/release_signing.key" in workflow
    assert "openssl pkey -in dist/release_signing.key -pubout -out dist/release_signing.pub" in workflow
    assert "--key dist/release_signing.key" in workflow
    assert "--key dist/release_signing.pub" in workflow
    release_block = workflow[workflow.index("name: Crear GitHub Release con el asset"):]
    assert "dist/release_signing.pub" in release_block


def test_pypi_workflow_signs_preflights_and_uploads_provenance_artifacts():
    workflow = (ROOT / ".github" / "workflows" / "publish-pypi.yml").read_text()
    assert "openssl genpkey -algorithm Ed25519 -out build/provenance/release_signing.key" in workflow
    assert "openssl pkey -in build/provenance/release_signing.key -pubout -out build/provenance/release_signing.pub" in workflow
    assert "--key build/provenance/release_signing.key" in workflow
    assert "--key build/provenance/release_signing.pub" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "build/provenance/sbom.cdx.json" in workflow
    assert "build/provenance/provenance.dsse.json" in workflow
    assert "build/provenance/release_signing.pub" in workflow
