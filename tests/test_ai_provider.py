import json
import os
import stat
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core import ai_provider


class FakeOpenAI(BaseHTTPRequestHandler):
    seen_auth = ""

    def log_message(self, *_args):
        pass

    def do_GET(self):
        FakeOpenAI.seen_auth = self.headers.get("Authorization", "")
        if self.path == "/v1/models":
            body = json.dumps({"data": [{"id": "test-model"}]}).encode()
            self.send_response(200)
        else:
            body = b"{}"
            self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        FakeOpenAI.seen_auth = self.headers.get("Authorization", "")
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        assert payload["model"] == "test-model"
        body = json.dumps({
            "id": "chatcmpl-test", "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "respuesta local"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeOpenAI)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    return srv


def test_save_masks_key_and_secures_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = ai_provider.save(root, {
            "enabled": True, "provider": "custom", "base_url": "http://127.0.0.1:9999/v1",
            "model": "model-x", "api_key": "super-secret-key",
        })
        assert result["ok"] is True
        status = ai_provider.status(root)
        raw = json.dumps(status)
        assert "super-secret-key" not in raw
        assert status["configured"] is True
        assert status["key_configured"] is True
        assert status["masked_key"].startswith("supe")
        assert stat.S_IMODE((root / "ai_provider.json").stat().st_mode) == 0o600
        assert stat.S_IMODE((root / ".env").stat().st_mode) == 0o600


def test_disabled_requires_no_key():
    with tempfile.TemporaryDirectory() as tmp:
        result = ai_provider.save(Path(tmp), {"enabled": False, "provider": "disabled"})
        assert result["ok"] is True
        assert ai_provider.status(Path(tmp))["configured"] is False


def test_rejects_non_http_provider_url():
    with tempfile.TemporaryDirectory() as tmp:
        result = ai_provider.save(Path(tmp), {
            "enabled": True, "provider": "custom", "base_url": "file:///etc", "model": "x",
        })
        assert result["ok"] is False


def test_rejects_newline_in_api_key():
    with tempfile.TemporaryDirectory() as tmp:
        result = ai_provider.save(Path(tmp), {
            "enabled": True, "provider": "custom", "base_url": "http://127.0.0.1:9999/v1",
            "model": "x", "api_key": "valid-prefix\nINJECTED=value",
        })
        assert result["ok"] is False
        assert list(Path(tmp).iterdir()) == []


def test_openai_compatible_test_and_chat():
    srv = _server()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = "http://127.0.0.1:%d/v1" % srv.server_port
            assert ai_provider.save(root, {
                "enabled": True, "provider": "custom", "base_url": base,
                "model": "test-model", "api_key": "provider-secret",
            })["ok"]
            tested = ai_provider.test_connection(root)
            assert tested["ok"] is True
            assert "test-model" in tested["models"]
            reply = ai_provider.chat(root, [{"role": "user", "content": "hola"}])
            assert reply["ok"] is True
            assert reply["text"] == "respuesta local"
            assert reply["response"]["object"] == "chat.completion"
            assert FakeOpenAI.seen_auth == "Bearer provider-secret"
    finally:
        srv.shutdown()
        srv.server_close()


def test_unsaved_values_do_not_mutate_tenant_root():
    srv = _server()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = ai_provider.test_values({
                "provider": "custom", "base_url": "http://127.0.0.1:%d/v1" % srv.server_port,
                "model": "test-model", "api_key": "ephemeral-secret",
            })
            assert result["ok"] is True
            assert list(root.iterdir()) == []
    finally:
        srv.shutdown()
        srv.server_close()
