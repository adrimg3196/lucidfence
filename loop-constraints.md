# Loop constraints

Structured constraints for the LucidFence improvement loop. Enforced by the
maintainer and the PR verifier (see `LOOP.md`).

## Denylist (never auto-merge / reject)

- Any commit or PR that adds secrets to `config.json`, `data/`, or `.env`.
- Modifications to `core/adapters/base.py` (the frozen `MDMAdapter` contract)
  without a major version bump.
- Publishing `data/cloud_state.json` with real tenant data (it is demo-only).
- PRs that embed cryptocurrency wallet addresses, payout instructions, or
  off-topic changes unrelated to geofencing / UEM.

## Push / merge rules

- `main` is protected: PR review required; no force-push.
- Auto-merge allowed ONLY for: loop scaffolding docs, `loop-audit` CI, and
  dependabot patches for loop tooling.
- Adapter contributions from the community MUST preserve the offline mock path
  and ship tests that run without real credentials.

## Human gates

- Adapter contract change → human.
- Desktop build / packaging change → human.
- Security posture change → human.
- Any change touching `saas_server.py` auth or `core/notifier.py` → human.
