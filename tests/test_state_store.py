"""StateStore must survive a single malformed record on disk.

Regression: _load() wrapped the whole load loop in one
`except Exception: self._states = {}`, so ONE bad row silently wiped ALL
persisted device state on every startup. A corrupt or schema-drifted record
must be skipped, not destroy the fleet's history.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.state_store import StateStore  # noqa: E402


def _seed(data_dir, rows):
    with open(os.path.join(data_dir, "device_states.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh)


def test_load_skips_malformed_record_without_losing_valid_ones():
    d = tempfile.mkdtemp()
    _seed(d, [
        {"device_id": "dev-a", "name": "A", "platform": "ios", "fence_state": "inside"},
        # forward-incompatible / corrupt row: unknown key raises in DeviceState(**d)
        {"device_id": "dev-bad", "name": "Bad", "platform": "ios", "no_such_field": True},
        {"device_id": "dev-c", "name": "C", "platform": "android", "fence_state": "outside"},
    ])
    store = StateStore(d)
    snap = store.snapshot()
    assert "dev-a" in snap, "valid record dev-a was lost on load"
    assert "dev-c" in snap, "valid record dev-c was lost on load"
    assert "dev-bad" not in snap, "malformed record should be skipped, not stored"


if __name__ == "__main__":
    test_load_skips_malformed_record_without_losing_valid_ones()
    print("PASS")
