# Durable night-shift manifests

This versioned directory is the durable home for verified
`lucidfence-night-shift-manifest/v1` snapshots. The trusted Actions workflow
first emits each manifest in its officially attested evidence bundle; a later
agent-managed PR may record those exact verified bytes here without rewriting
an earlier run.

The storage contract is closed and versioned. `scripts/verify.py` accepts only
this layout (the `v1/` directory is absent while history is empty):

```text
runs/
  README.md
  v1/
    run-<run-id>-attempt-<run-attempt>-head-<40-hex-head-sha>/
      manifest.json
      attestation.bundle.jsonl
      trusted-root.jsonl
      evidence/
        <every and only artifact named by manifest.json>
```

The directory name must match the manifest run ID, attempt and head SHA. A
bundle has exactly the four entries above, and `evidence/` has exactly the
manifest inventory. Symlinks, loose manifests, extra files, missing files,
non-canonical JSON and byte-level digest drift fail closed.

The repository intentionally starts with no synthetic run history. A manifest
must not be committed here unless the offline verifier accepts its full
artifact set and reruns official GitHub CLI cryptographic verification against
`attestation.bundle.jsonl`. For every non-empty store, invoke
`scripts/verify.py --attestation-trusted-root PATH` with GitHub trusted-root
bytes obtained through an independent official channel outside `runs/`. The
co-packaged `trusted-root.jsonl` is an untrusted historical record and is never
used as the cryptographic root. A stored verification-result JSON is never
accepted as proof; it is regenerated in temporary storage on every gate.

Archive verification evaluates the seven-day validity window at the trusted
run's generation time, so an immutable historical bundle remains verifiable.
Using that evidence for a current merge still evaluates expiry against current
time and rejects stale evidence.
