"""Shared-filesystem active/passive lease for LucidFence HA.

Only the lease holder may start a writer server. A standby process retries after
the active process exits; the OS releases flock automatically on crash.
"""
from __future__ import annotations

import fcntl
import json
import os
import socket
import time
from pathlib import Path


class ClusterLease:
    def __init__(self, data_root: Path, node_id: str | None = None):
        self.path = Path(data_root) / "_cluster.leader"
        self.node_id = node_id or f"{socket.gethostname()}:{os.getpid()}"
        self._handle = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return False
        self._handle = handle
        self.heartbeat()
        return True

    def heartbeat(self) -> None:
        if self._handle is None:
            return
        payload = {"node_id": self.node_id, "pid": os.getpid(),
                   "heartbeat": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        self._handle.seek(0); self._handle.truncate(); self._handle.write(json.dumps(payload) + "\n"); self._handle.flush(); os.fsync(self._handle.fileno())

    @property
    def acquired(self) -> bool:
        return self._handle is not None

    def release(self) -> None:
        if self._handle is None:
            return
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close(); self._handle = None

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("another LucidFence node holds the writer lease")
        return self

    def __exit__(self, *_):
        self.release()
