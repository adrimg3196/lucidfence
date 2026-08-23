"""Cross-UEM identity reconciliation without auto-fusion (dictamen §3, C4).

``normalize_identity()`` from ``multiuem.py`` is reused to canonicalize the
device identifiers each UEM reports. We then build a *correlation key* and emit a
``Reconciliation`` record that exposes the linkage with a confidence score.

Red line C4: ``auto_fused`` is ALWAYS ``False``. LucidFence correlates and shows
candidate links; it never merges two UEM records into one canonical identity on
its own. A human/tenant confirms any merge.
"""
from __future__ import annotations

from typing import Iterable, Optional

from lucidfence.core.multiuem import normalize_identity

from .types import Reconciliation


def reconcile_identity(
    *,
    method: str,
    candidate_ids: Iterable[str | None],
    known_device_ids: Optional[set[str]] = None,
    now_seen_cycle: int = 0,
) -> Reconciliation:
    """Correlate candidate device identifiers across UEMs.

    ``known_device_ids``: device IDs LucidFence already knows for this tenant
    (from adapters). A normalized ``candidate_id`` that is already a known id is
    a STRONG link (confidence 1.0); otherwise it is a WEAK candidate (lower
    confidence) registered but NEVER auto-merged.

    Returns a ``Reconciliation`` with ``auto_fused=False`` always.
    """
    known = {normalize_identity(x) for x in (known_device_ids or set())}
    norm_candidates = [c for c in (normalize_identity(x) for x in candidate_ids) if c]

    linked: list[str] = []
    confidence = 0.0
    for cid in dict.fromkeys(norm_candidates):  # unique, order-preserving
        if cid in known:
            linked.append(cid)
            # Strong link dominates confidence.
            confidence = max(confidence, 1.0)
        # Weak candidates are recorded via candidate_ids (set below), never merged.

    if linked:
        # All linked ids agree with a known record -> high confidence.
        conf = 1.0
    elif norm_candidates:
        # No exact known match: probabilistic candidate only.
        conf = 0.4
    else:
        conf = 0.0

    return Reconciliation(
        method=method,
        confidence=conf,
        linked_ids=linked,
        candidate_ids=norm_candidates,
        auto_fused=False,
    )
