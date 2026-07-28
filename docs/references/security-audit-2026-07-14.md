# Security Audit — LucidFence (OWASP Top 10 + framework checklist)
Date: 2026-07-14 · Scope: diff main~5..main + named files · Auditor: security-auditor

## Verdict: PASS_WITH_NOTES
No Critical/High (no secrets leaked, no crypto failure, multi-tenant isolation holds). Several Medium issues to fix before any internet-facing (Fly) deployment.

## PASS (verified)
- **No secrets in repo**: grep password/secret/api_key/token/key/bearer over diff + cloud_state.json + data/cloud_tenants = 0 hits. .gitignore covers .env, *.local.json, config.json, _users/_sessions.
- **Multi-tenant isolation**: cloud_publisher iterates separate `data/cloud_tenants/<id>/` dirs; saas_server scopes each org to its own `data_dir`+Engine. `active_org()` rejects a forged `gf_org` cookie if it isn't in `user["org_roles"]` (no cross-org escalation). Every API checks RBAC via `require(cap)`.
- **No /api/auth/demo in prod**: routing implements only signup/login/logout/me. The loopback demo endpoint referenced in a comment does NOT exist — no anonymous-auth bypass. (Comment at saas_server.py:275 is stale/misleading — cleanup suggested.)
- **cloud_state.json exposes no secrets**: public demo data by design; CVE/SOAR blocks are flagged `"demo": true`.

## MEDIUM
- **M1 — install.sh runs dependency lifecycle un-reviewed** (checklist §Dependency Security): executes `pip install -r requirements.txt` and `docker compose up --build` with no verification gate; also downloads `docker-compose.yml` from raw.githubusercontent with no checksum. Plus the documented `curl …/install.sh | bash` (curl|sh) supply-chain pattern.
- **M2 — docker-compose/docker_start network exposure**: `ports: "8765:8765"` publishes on 0.0.0.0 with no TLS (plaintext login). `docker_start.sh` binds MoA on `0.0.0.0:8085` (unauthenticated AI endpoint) inside Fly VM.
- **M3 — No login rate limiting** (OWASP A07): `/api/auth/login` + `/api/auth/signup` have no throttle/lockout; only 100k-round PBKDF2. Brute-force feasible once internet-exposed.
- **M4 — 500 error leaks internals** (OWASP A05/A09): `do_GET/do_POST` return `{"error":"server_error","detail": str(e)}`, exposing exception text/traceback. Checklist Error Handling violated.

## LOW
- **L1**: `do_DELETE` skips the `_host_allowed` Host guard (CSRF/DNS-rebind inconsistency vs GET/POST).
- **L2**: `_send_file` (static HTML/JS) omits the CSP/`X-Frame-Options`/`nosniff` headers that `_send_json` sets.
- **L3**: `deploy-fly.yml` `curl -L https://fly.io/install.sh | sh` runs unverified external script.
- **L4**: KDF is pure-Python PBKDF2-100k (checklist recommends bcrypt/scrypt/argon2); low rounds, acceptable but weak.

## Recommended gates before merge to internet-facing
1. install.sh: verify checksums / block-and-review deps; sign or pin install.sh.
2. Bind 8765 to 127.0.0.1 + mandatory TLS reverse proxy; bind MoA to 127.0.0.1 only.
3. Add login rate-limit + lockout; raise KDF rounds or switch to scrypt/argon2.
4. Replace verbose 500 detail with generic error; add Host guard to DELETE; add security headers to static files.
