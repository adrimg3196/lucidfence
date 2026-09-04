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
        # corrupt row: required fields missing -> DeviceState(**d) raises -> skipped
        {"device_id": "dev-bad", "fence_state": "inside"},
        # forward-compatible row: a key written by a NEWER build (then rollback)
        # is ignored, the device is KEPT. Dropping it made the engine see the
        # device as first-sighted and re-fire on_enter across the fleet.
        {"device_id": "dev-new", "name": "New", "platform": "ios", "fence_state": "inside",
         "no_such_field": True},
        {"device_id": "dev-c", "name": "C", "platform": "android", "fence_state": "outside"},
    ])
    store = StateStore(d)
    snap = store.snapshot()
    assert "dev-a" in snap, "valid record dev-a was lost on load"
    assert "dev-c" in snap, "valid record dev-c was lost on load"
    assert "dev-bad" not in snap, "malformed record should be skipped, not stored"
    assert "dev-new" in snap and snap["dev-new"].fence_state == "inside", (
        "row with an unknown (newer-build) key must be kept, not dropped")


if __name__ == "__main__":
    test_load_skips_malformed_record_without_losing_valid_ones()
    print("PASS")
