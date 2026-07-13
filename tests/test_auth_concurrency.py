"""Regression: concurrent HTTP threads must not race on auth JSON temp files."""
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from saas.auth import AuthStore


def test_concurrent_session_persistence_is_atomic():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = AuthStore(root)
        user = store.create_user("owner@example.test", "Owner", "password123", "org-test")
        with ThreadPoolExecutor(max_workers=12) as pool:
            tokens = list(pool.map(lambda _: store.create_session(user.id), range(40)))
        assert len(tokens) == len(set(tokens)) == 40
        persisted = json.loads((root / "_sessions.json").read_text(encoding="utf-8"))
        assert all(token in persisted for token in tokens)
        assert not list(root.glob("*.tmp")), "temporary auth files leaked"
