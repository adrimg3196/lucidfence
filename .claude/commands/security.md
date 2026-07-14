---
description: Security audit and hardening pass for LucidFence
---

Invoke security-and-hardening adapted to LucidFence.

Run a vulnerability + threat-model pass using `references/security-checklist.md`:
- OWASP Top 10, secrets handling, auth/authz, dependency CVEs (`pip-audit`).
- Multi-tenant isolation: one tenant must not read another's devices/geocercas.
- No `/api/auth/demo` or any demo shortcut in production (test enforces this).
- No secrets in repo; `.env.example` placeholders only.
- MoA output treated as untrusted (no eval/SQL/shell/innerHTML).

Output the standard audit report. Critical/High findings are launch blockers.
File what you find, then enforce on new changes.
