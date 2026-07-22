# Multi-UEM Tenant-Local Geofencing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ejecutar varios UEM simultáneamente por tenant, consolidar dispositivos con procedencia y evaluar geofencing solo con evidencia de ubicación apta, enrutando acciones al proveedor remoto correcto.

**Architecture:** Añadir un dominio `core/multiuem.py` independiente del contrato congelado `MDMAdapter`; envolver cada fuente/adapter como `ProviderBinding`; hacer que `MultiUEMOrchestrator` implemente el seam `fetch()` que ya consume `Engine` y el seam `execute()` que ya usa para acciones. La configuración legacy permanece intacta cuando `uem.providers` no está presente.

**Tech Stack:** Python 3.11, dataclasses/stdlib, servidor HTTP propio, vanilla JS, runner `tests/run_tests.py`, Playwright ya instalado por el proyecto.

## Global Constraints

- Local-first: datos y credenciales permanecen en el directorio del tenant.
- Sin cambios breaking en `core.adapters.base.MDMAdapter`.
- Sin dependencias nuevas salvo que sean imprescindibles y aprobadas; este plan no requiere ninguna.
- Una ubicación rechazada produce `unknown`, nunca `outside`.
- Acciones destructivas permanecen human-gated; el slice solo enruta llamadas que el engine ya autorizó.
- Proveedor caído produce degradación parcial y error sanitizado, no fallo total.
- Placeholders de identidad nunca deduplican dispositivos.
- No exponer tokens, headers, cuerpos remotos ni secretos en API/logs/tests.
- Cada comportamiento nuevo sigue RED → GREEN → REFACTOR y se observa fallar antes de producción.
- La suite completa y el navegador vivo deben pasar antes de finalizar.

---

### Task 1: Dominio normalizado y gate de evidencia

**Files:**
- Create: `core/multiuem.py`
- Create: `tests/test_multiuem_domain.py`

**Interfaces:**
- Produces: `ProviderCapabilities`, `LocationEvidence`, `NormalizedDevice`, `ProviderHealth`, `SyncResult`.
- Produces: `normalize_identity(value) -> str | None`.
- Produces: `LocationEvidence.quality(now, max_age_seconds, max_accuracy_m, future_tolerance_seconds=60) -> tuple[bool, str]`.
- Consumes: solo stdlib.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timedelta, timezone
from core.multiuem import LocationEvidence, normalize_identity


def test_identity_placeholders_are_never_usable():
    for value in (None, "", "N/A", "unknown", "0", " - "):
        assert normalize_identity(value) is None
    assert normalize_identity(" ab-c 123 ") == "ABC123"


def test_location_quality_accepts_fresh_precise_evidence():
    now = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    evidence = LocationEvidence(40.42, -3.71, now.isoformat(), 25, "intune", "gps")
    assert evidence.quality(now, 900, 200) == (True, "accepted")


def test_location_quality_rejects_stale_inaccurate_future_and_invalid_coordinates():
    now = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    cases = [
        (LocationEvidence(40.42, -3.71, (now-timedelta(seconds=901)).isoformat(), 25, "jamf", "gps"), "stale"),
        (LocationEvidence(40.42, -3.71, now.isoformat(), 201, "jamf", "gps"), "inaccurate"),
        (LocationEvidence(40.42, -3.71, (now+timedelta(seconds=61)).isoformat(), 25, "jamf", "gps"), "future"),
        (LocationEvidence(100, -3.71, now.isoformat(), 25, "jamf", "gps"), "invalid_coordinates"),
    ]
    for evidence, reason in cases:
        assert evidence.quality(now, 900, 200) == (False, reason)
```

- [ ] **Step 2: Run RED**

Run: `/Users/adri/geofence-uem/.venv/bin/python -m pytest tests/test_multiuem_domain.py -q`
Expected: FAIL con `ModuleNotFoundError: core.multiuem`.

- [ ] **Step 3: Implement the minimal domain**

Implement dataclasses frozen where practical. `LocationEvidence.quality` must parse ISO8601 including `Z`, reject booleans/non-numbers, enforce latitude `[-90,90]`, longitude `[-180,180]`, future tolerance, age and optional accuracy. `normalize_identity` must remove all non-alphanumeric characters, uppercase, and reject `{NA,NONE,NULL,UNKNOWN,UNAVAILABLE,0}` after normalization.

Required public signatures:

```python
@dataclass(frozen=True)
class ProviderCapabilities:
    inventory: bool = True
    location: bool = False
    native_geofences: bool = False
    actions: frozenset[str] = frozenset()

@dataclass(frozen=True)
class LocationEvidence:
    lat: float
    lng: float
    observed_at: str | None
    accuracy_m: float | None
    provider: str
    source: str
    def quality(self, now: datetime, max_age_seconds: int,
                max_accuracy_m: float, future_tolerance_seconds: int = 60) -> tuple[bool, str]: ...

@dataclass
class NormalizedDevice:
    canonical_id: str
    provider: str
    provider_device_id: str
    name: str
    platform: str
    serial_number: str | None = None
    imei: str | None = None
    compliant: bool | None = None
    status: str = "unknown"
    location: LocationEvidence | None = None
    inventory: dict = field(default_factory=dict)
    provider_refs: dict[str, str] = field(default_factory=dict)
    provenance: dict[str, str] = field(default_factory=dict)
    identity_conflict: bool = False
```

- [ ] **Step 4: Run GREEN and refactor**

Run: `/Users/adri/geofence-uem/.venv/bin/python -m pytest tests/test_multiuem_domain.py -q`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add core/multiuem.py tests/test_multiuem_domain.py
git commit -m "feat(multiuem): add normalized device and location evidence"
```

---

### Task 2: Consolidación, aislamiento y enrutado del orquestador

**Files:**
- Modify: `core/multiuem.py`
- Create: `tests/test_multiuem_orchestrator.py`

**Interfaces:**
- Consumes: modelos de Task 1.
- Produces: `ProviderBinding(name, capabilities, fetch_devices, execute_action)`.
- Produces: `MultiUEMOrchestrator(bindings, max_location_age_seconds=900, max_accuracy_m=500)`.
- Produces: `sync(now=None) -> SyncResult`, `fetch() -> list[LocationReport]`, `execute(device, action, params, dry_run=False) -> dict`, `health() -> dict`.

- [ ] **Step 1: Write RED tests for partial failure and deterministic merge**

Use in-memory bindings; no network mocks. Provider A returns device `a-1` with serial `SER-1` and stale location. Provider B returns `b-7` with serial `ser1`, fresh location and a different inventory field. Provider C raises `TimeoutError("token=must-not-leak")`.

Assertions:

```python
result = orchestrator.sync(now=fixed_now)
assert len(result.devices) == 1
merged = result.devices[0]
assert merged.provider_refs == {"applivery": "a-1", "intune": "b-7"}
assert merged.location.provider == "intune"
assert result.health["jamf"].status == "error"
assert "token=" not in result.health["jamf"].detail
assert result.status == "degraded"
```

Add a second test where both records use serial `N/A`; assert two devices and no merge. Add a third where one serial collides with one device and IMEI collides with another; assert records stay separate with `identity_conflict=True`.

- [ ] **Step 2: Run RED**

Run: `/Users/adri/geofence-uem/.venv/bin/python -m pytest tests/test_multiuem_orchestrator.py -q`
Expected: FAIL because orchestrator types are absent.

- [ ] **Step 3: Implement sync and merge**

Rules:

1. Catch `Exception` per provider boundary only.
2. Health error detail is exactly the exception class name, never `str(exc)`.
3. Candidate identity keys are valid normalized serial and IMEI.
4. Merge only when all matching strong keys point to the same canonical record.
5. Conflict means no automatic merge and marks every involved record.
6. Choose location among accepted candidates by parsed `(observed_at desc, accuracy asc, provider name asc)`; never compare timestamp strings lexicographically.
7. Merge compliance conservatively: any explicit `False` dominates `True`, which dominates `None`.
8. Preserve provider references for action routing and field-level provenance for every selected inventory value.
9. For equal-quality inventory values, use provider name ascending as deterministic tie-breaker; never depend on binding iteration order.
10. `status` is `ok`, `degraded`, or `error` based on provider outcomes.

- [ ] **Step 4: Write and run RED action-routing tests**

```python
response = orchestrator.execute(
    {"device_id": canonical_id, "provider": "intune", "provider_device_id": "b-7"},
    "lock", {}, dry_run=True,
)
assert calls == [("b-7", "lock", {}, True)]
assert response["adapter"] == "intune"
```

Also assert unsupported action returns `{ok: False, error_type: "unsupported_action"}` and unknown provider returns structured failure without raising.

- [ ] **Step 5: Implement routing and run GREEN**

Run: `/Users/adri/geofence-uem/.venv/bin/python -m pytest tests/test_multiuem_orchestrator.py -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add core/multiuem.py tests/test_multiuem_orchestrator.py
git commit -m "feat(multiuem): orchestrate providers with safe identity merge"
```

---

### Task 3: Provider wrappers and tenant configuration

**Files:**
- Create: `core/multiuem_providers.py`
- Create: `core/outbound_security.py`
- Modify: `config_loader.py`
- Modify: `core/secrets.py`
- Modify: `saas_server.py` (`_apply_tenant_integration`, connector persistence only)
- Modify: `core/location_source.py`
- Modify: `core/adapters/applivery.py`
- Modify: `core/adapters/intune.py`
- Modify: `core/adapters/jamf.py`
- Modify: `core/adapters/workspace_one.py`
- Modify: `core/adapters/chromeos.py`
- Modify: `core/adapters/windows_conformidad.py`
- Modify: `.env.example`
- Create: `tests/test_multiuem_providers.py`
- Create: `tests/test_connector_credentials_isolation.py`
- Create: `tests/test_uem_outbound_security.py`

**Interfaces:**
- Consumes: `LiveLocationSource`, `SimulationLocationSource`, registered adapters and their `execute(..., "list", ...)` behavior.
- Produces: `build_multiuem_orchestrator(config: dict) -> MultiUEMOrchestrator | None`.
- Produces: `uem.providers` normalized list; disabled providers are ignored.

- [ ] **Step 1: Write RED configuration tests**

Test a config containing two enabled providers and one disabled provider. Secrets are fake obvious fixtures (`test-only-*`). Assert exactly two bindings, stable order, declared capabilities and no process-env fallback when the provider block explicitly contains an empty credential field.

Test no `uem.providers`: builder returns `None` so legacy behavior remains active.

Add a tenant-isolation test with two temporary tenant roots and different fake
credentials for Intune and Jamf. Assert each binding receives only its tenant's
credential, a missing tenant credential never falls back to the process
environment, rotating tenant A does not change tenant B, and serialized health
contains no secret fields or values.

- [ ] **Step 2: Run RED**

Run: `/Users/adri/geofence-uem/.venv/bin/python -m pytest tests/test_multiuem_providers.py -q`
Expected: FAIL because builder does not exist.

- [ ] **Step 3: Implement wrappers**

Provider fetch wrappers must output `NormalizedDevice`. Applivery wraps `LiveLocationSource.fetch()`. Other built-ins call their list/report seam only when supported; an adapter without inventory capability remains action-only and reports zero inventory rather than fabricating devices. Constructors must not perform network calls.

Extend the existing tenant integration document to store provider blocks below
`integration.json` with mode `0600`. `core/secrets.py` must return a provider
credential mapping scoped to one tenant. `_apply_tenant_integration` passes that
mapping into config explicitly. Provider builders must not read process-global
credentials once an explicit tenant provider block exists, including when its
credential value is empty.

`.env.example` documents names only with placeholders and includes no usable credential. Keep all live modes opt-in.

Use explicit `str | None` constructor semantics: `None` permits legacy environment lookup; an explicit empty string means “tenant configured but missing” and never falls back to process globals. Adapter methods must not re-read environment variables after construction.

Verified capability matrix:
- Applivery: live inventory + location after hardening; no native action capability until its undocumented endpoint is independently validated.
- Intune: live inventory + declared Graph actions; no location.
- Jamf: live inventory/actions only after public tenant-host validation; otherwise unavailable, never mock-as-live.
- Workspace ONE: live inventory/actions after host validation; profile export is not `native_geofences`.
- ChromeOS: live report/inventory, no actions/location.
- Windows: report-only and disabled when Intune already supplies the same Windows inventory.

- [ ] **Step 4: Add URL safety tests before enabling configurable live endpoints**

Create one shared outbound policy. Reject non-HTTPS, userinfo, query/fragment, localhost, loopback, link-local, RFC1918, CGNAT, multicast/reserved and any hostname with non-public A/AAAA. Revalidate on connection. Authenticated/token requests disable redirects. Pagination is same-origin, bounded and cycle-detected. Pin fixed public origins for Applivery, Microsoft Graph/login and Google Admin/OAuth. Jamf/Workspace ONE tenant hosts fail closed when public DNS validation cannot be established.

- [ ] **Step 5: Run GREEN and contract regression**

Run:

```bash
/Users/adri/geofence-uem/.venv/bin/python -m pytest tests/test_multiuem_providers.py tests/test_connector_credentials_isolation.py tests/test_uem_outbound_security.py tests/test_tenant_credentials.py tests/test_sdk_contract.py tests/test_adapters_intune_live.py tests/test_adapters_jamf_live.py -q
```

Expected: all pass; frozen adapter contract unchanged.

- [ ] **Step 6: Commit**

```bash
git add core/multiuem_providers.py core/outbound_security.py config_loader.py core/secrets.py saas_server.py core/location_source.py core/adapters .env.example tests/test_multiuem_providers.py tests/test_connector_credentials_isolation.py tests/test_uem_outbound_security.py
git commit -m "feat(multiuem): connect tenant providers with hardened transport"
```

---

### Task 4: Engine integration and fail-closed geofence transitions

**Files:**
- Modify: `core/engine.py`
- Modify: `core/state_store.py`
- Modify: `core/location_source.py`
- Create: `tests/test_multiuem_engine.py`
- Create: `tests/test_location_evidence_transitions.py`

**Interfaces:**
- Consumes: `build_multiuem_orchestrator(config)` and its `fetch/execute/health` seams.
- Produces: `DeviceState.provider`, `provider_device_id`, `provider_refs`, `location_quality`, `location_rejection_reason`.
- Preserves: legacy `self.source` and `self.adapter` when no Multi-UEM config exists.

- [ ] **Step 1: Write RED engine tests**

Build a hermetic config with two in-memory provider bindings injected through `config["_multiuem_orchestrator"]` (test-only dependency seam). Assert:

1. both providers contribute in one `run_once()`;
2. one merged canonical device is persisted once;
3. stale/imprecise evidence persists as `fence_state="unknown"` and produces no `exit` event or destructive action;
4. a fresh second cycle changes `inside -> outside` and routes the action using the provider remote ID;
5. provider health appears in `last_stats["uem_providers"]`;
6. legacy config still passes an existing engine route test unchanged.

Add regression tests that reproduce the audited P0s:

1. Applivery `lastLocation.agent.accuracy` reaches `LocationReport.accuracy_m`;
2. `inside(hq) -> outside(None)` executes the `hq` action configured for
   `on_exit`, using the previous fence rather than the current `None`;
3. `inside(hq) -> unknown(None)` executes only safe `on_unknown` notification
   behavior and never a destructive action;
4. persisted transition events expose explicit `kind` in
   `{enter, exit, unknown, recovered}` so the existing UI filters work;
5. stale or inaccurate evidence cannot create an exit or route-exit event.

- [ ] **Step 2: Run RED**

Run: `/Users/adri/geofence-uem/.venv/bin/python -m pytest tests/test_multiuem_engine.py -q`
Expected: FAIL because Engine ignores the orchestrator and state lacks fields.

- [ ] **Step 3: Implement minimal engine seam**

At initialization:

```python
multi = config.get("_multiuem_orchestrator") or build_multiuem_orchestrator(config)
if multi is not None:
    self.source = multi
    self.adapter = multi
    self.multiuem = multi
else:
    # existing legacy construction unchanged
```

During each report, copy provider/provenance/quality fields into `DeviceState`. The orchestrator's `fetch()` must omit rejected coordinates (lat/lng `None`) but retain rejection metadata on the report, causing existing geometry code to choose `unknown`.

When a transition leaves a fence, pass both previous and current state to the
action dispatcher. Resolve `on_exit` and `on_unknown` against the previous
fence ID. Reject destructive actions for an `unknown` transition regardless of
fence configuration. Emit the explicit transition `kind`; do not infer it in
the UI. Preserve Applivery accuracy in `_extract_last_location()`.

Do not duplicate fence geometry or policy logic.

- [ ] **Step 4: Run GREEN plus legacy engine tests**

Run:

```bash
/Users/adri/geofence-uem/.venv/bin/python -m pytest tests/test_multiuem_engine.py tests/test_location_evidence_transitions.py tests/test_engine_routes.py tests/test_risk_evidence_gate.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add core/engine.py core/state_store.py core/location_source.py tests/test_multiuem_engine.py tests/test_location_evidence_transitions.py
git commit -m "feat(engine): consume multi-UEM evidence fail closed"
```

---

### Task 5: Google and generic OIDC SSO

**Files:**
- Create: `core/oidc.py`
- Modify: `saas/auth.py`
- Modify: `saas_server.py` (auth routes only)
- Modify: `pyproject.toml`
- Modify: `requirements.lock`
- Modify: `sbom.cdx.json`
- Modify: `.env.example`
- Create: `tests/test_oidc_sso.py`

**Interfaces:**
- Produces: `OIDCProvider`, `OIDCFlowStore`, `OIDCClient`.
- Produces: `OIDCMetadataValidator` and `IDTokenValidator`, backed by pinned `PyJWT[crypto]`; no handwritten signature verification.
- Produces: `GET /api/auth/sso/providers`,
  `GET /api/auth/sso/<provider>/start`, and
  `GET /api/auth/sso/<provider>/callback`.
- Persists account links by `(issuer, subject)`; never auto-links by email.
- Google is a preset configuration; Entra ID, Okta and other providers use the
  same generic OIDC contract.

- [ ] **Step 1: Write RED domain and HTTP-flow tests**

Use a fake HTTPS transport and fake obvious credentials. Assert:

1. start creates 256-bit `state`, `nonce` and PKCE verifier, stores them
   server-side with a ten-minute maximum TTL, and emits a S256 challenge;
2. callback consumes state exactly once and rejects missing, expired, replayed
   or mismatched state before token exchange;
3. redirect URI is exact and return paths are relative allowlisted paths;
4. discovery/token/JWKS/userinfo endpoints must be HTTPS and pass an injectable public-egress policy on every connection; redirects are disabled;
5. ID Token rejects invalid signature, `alg=none`, HS/RS confusion, unknown or stale `kid`, issuer mismatch, invalid `aud`/`azp`, expiry, future `iat`, and absent/mismatched/replayed nonce; bounded JWKS refresh is tested;
6. authorization response mix-up is rejected: state A through provider B, response `iss=B`, or token endpoint B causes zero wrong-endpoint calls/leaks;
7. userinfo requires `sub` equal to the validated ID Token and verified email when email is used for provisioning;
8. two providers with the same email but different `(issuer, sub)` are not silently merged;
9. raw client secret, code, verifier, access token and ID token never appear in API responses, exceptions, logs or persisted user records;
10. disabled/unconfigured SSO returns a non-secret provider list and structured failure, while password login remains functional.

Add RED tests for duplicated callback parameters, `code+error`, stolen state in another browser, concurrent callbacks, Host/forwarded-header poisoning, absolute/protocol-relative/double-encoded return paths, IPv4/IPv6 private and mapped addresses, mixed/rebinding DNS, cross-origin redirects, oversized metadata/JWKS/token bodies, token timeout after send, session fixation, logout revocation and callback-query log redaction.

- [ ] **Step 2: Run RED**

Run: `/Users/adri/geofence-uem/.venv/bin/python -m pytest tests/test_oidc_sso.py -q`
Expected: FAIL because `core.oidc` and SSO routes do not exist.

- [ ] **Step 3: Implement generic Authorization Code + PKCE**

Use pinned `PyJWT[crypto]` for JWS/JWKS and an injectable no-redirect transport. Never accept tokens from the browser. Validate the ID Token before optional UserInfo. State is persisted server-side `0600`, capacity-bounded, purged and consumed atomically, and bound to a host-only pre-auth cookie. Exposed errors are stable codes only.

Token endpoint authentication is an explicit allowlist: hosted prefers `client_secret_basic`; `client_secret_post` is opt-in and `none` is restricted to a separate loopback public-client registration. Secrets never enter URLs. The redirect URI comes only from trusted config and is byte-identical in authorize and token exchange.

Extend `User` compatibly with `external_identities: list[dict]` using a default
factory. Existing password users must load unchanged. Add an AuthStore index on
`(issuer, subject)` and an explicit linking/provisioning method. Provisioning
requires either a pre-authorized external identity/invitation or a configured
verified domain + target organization/role; owner bootstrap is a separate,
explicit one-time policy.

Separate `purpose=login|link|owner-bootstrap`. Linking requires an authenticated user, CSRF and recent reauthentication. Invitations are single-use, expiring and bound to org/role/canonical identity. Owner bootstrap is opt-in, audited and disabled permanently after first use.

- [ ] **Step 4: Implement Google preset and generic provider config**

Google defaults to issuer `https://accounts.google.com`; client ID, client
secret, redirect URI, allowed domains and provisioning policy are deployment
secrets. Generic providers require explicit issuer/discovery URL. `.env.example`
contains placeholders only. The provider-list endpoint exposes name/label/enabled
only.

Discovery starts only from admin config, requires exact metadata issuer, validates every endpoint and A/AAAA, revalidates on connect, disables redirects and bounds responses. Hosted requests only `openid email profile`, never `offline_access`, and persists no provider tokens.

`OIDCMetadataValidator` canonicalizes issuer/endpoints before DNS: HTTPS, valid DNS hostname or canonical IP, no userinfo/query/fragment/backslash/ambiguous escapes, and only allowlisted ports. Discovery's issuer is byte-identical to configured issuer. For every attempt, resolve a fresh A/AAAA snapshot and reject if any address is loopback, private, link-local, ULA, CGNAT, multicast, unspecified, reserved, IPv4-mapped private or cloud metadata. Reject non-canonical decimal/octal/hex IP forms and mixed public/private DNS. `PinnedHTTPSConnection` connects only to one IP from that snapshot without a second DNS lookup, while retaining the original hostname for Host, SNI and certificate verification; alternatively peer IP must be verified before any request/header/secret is sent. Every retry and JWKS refresh repeats this process. Discovery/token/JWKS/UserInfo never follow redirects.

The pre-auth cookie is random, ephemeral and host-only: `Secure` in hosted, `HttpOnly`, `SameSite=Lax`, `Path=/`, no `Domain`; it expires on consume or flow TTL. Callback compares the binding in constant time and fails before token exchange when missing or from another browser.

`OIDCFlowStore.consume()`, uniqueness of `(issuer, subject)`, invitation/owner-bootstrap mutation, user create/link and session issue share one transaction lock. This JSON-backed slice is explicitly single-process and startup fails if configured for multiple workers. Durable writes use a tempfile in the same directory, `0600`, flush, `fsync`, `os.replace`, then directory `fsync`. Concurrent callbacks create exactly one session and at most one user/link.

SSO sessions have configurable absolute TTL and server-side idle timeout. Success revokes pre-auth and any old session ID, generates a new cryptographic ID, and sets `Max-Age`/`Expires` consistent with TTL. Client-supplied session IDs are never reused.

`(issuer, subject)` is globally unique to one user. Invitation, identity, user and owner-bootstrap check/write is atomic. RED tests cover concurrent provisioning, simultaneous links to different accounts, invitation replay and partial persistence failure; exactly one contender wins.

Callback validates unique parameters and consumes state atomically before branching to `code` or `error`; an OP error also invalidates state/nonce. A timeout after sending code to the token endpoint consumes the code and is never retried automatically.

Local SSO accepts only `http://127.0.0.1:<port>/<exact-path>` or `http://[::1]:<port>/<exact-path>`. Reject `localhost`, DNS names, LAN, wildcard, `0.0.0.0`, wrong port/path. The listener binds only the registered loopback IP; an ephemeral listener uses neither `SO_REUSEADDR` nor `SO_REUSEPORT` and closes after the first valid callback or TTL.

After success, destroy pre-auth/old sessions, mint a fresh session, set a host-only `Secure; HttpOnly; SameSite=Lax; Path=/` cookie and return 303 to an enum-backed clean path with no-store/no-referrer headers. Logout always revokes the local session. Redact callback queries from HTTP access logs.

- [ ] **Step 5: Run GREEN and auth regressions**

Run:

```bash
/Users/adri/geofence-uem/.venv/bin/python -m pytest tests/test_oidc_sso.py tests/test_auth_concurrency.py tests/test_security_hardening.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add core/oidc.py saas/auth.py saas_server.py pyproject.toml requirements.lock sbom.cdx.json .env.example tests/test_oidc_sso.py
git commit -m "feat(auth): add secure Google and generic OIDC SSO"
```

---

### Task 6: Hosted login, local ownership, health API and admin-console evidence

**Files:**
- Modify: `saas_server.py`
- Modify: `saas/auth.py`
- Modify: `bin/lucidfence` only if bind validation is not already centralized
- Modify: `static/app.js`
- Modify: `static/i18n.js`
- Modify: `docs/openapi.json`
- Create: `tests/test_multiuem_api.py`
- Create: `tests/test_deployment_auth_modes.py`
- Modify: `tests/test_webapp_e2e_dashboard.py`

**Interfaces:**
- Produces: authenticated `GET /api/uem/providers` with tenant engine health/capabilities/coverage.
- Produces: device JSON fields from Task 4.
- Produces: explicit deployment mode `hosted|local`; hosted requires login,
  local loopback permits local-owner bootstrap without a cloud account, and a
  non-loopback local bind fails closed unless local authentication is enabled.
- UI consumes the endpoint and renders provider chips, sync status and location quality/reason.
- UI consumes `/api/auth/sso/providers` and renders only enabled SSO buttons;
  callback errors are generic and never expose provider tokens or codes.

- [ ] **Step 1: Write RED API tests**

Assert unauthenticated request is 401, viewer with `device:read` can read, tenant A cannot observe provider configuration/errors from tenant B, payload contains no key matching `token|secret|password|authorization|cookie`, and error detail is sanitized.

In `tests/test_deployment_auth_modes.py`, assert:

1. `hosted` rejects anonymous provider/device reads and accepts a real login
   session scoped to its organization;
2. `local` on loopback creates a local owner session without any cloud/network
   identity provider or signup dependency;
3. `local` bound to a non-loopback address refuses startup/config validation
   unless local authentication is explicitly enabled;
4. hosted and local both construct the same `MultiUEMOrchestrator` type and can
   activate two providers in one tenant cycle;
5. local mode never serializes or transmits credentials to a central endpoint.

- [ ] **Step 2: Run RED**

Run: `/Users/adri/geofence-uem/.venv/bin/python -m pytest tests/test_multiuem_api.py -q`
Expected: FAIL/404 because endpoint is absent.

- [ ] **Step 3: Implement endpoint and OpenAPI contract**

Response shape:

```json
{
  "status": "ok|degraded|error|legacy",
  "providers": [
    {
      "name": "intune",
      "status": "ok|error|disabled",
      "devices": 12,
      "location_accepted": 10,
      "location_rejected": 2,
      "capabilities": {"inventory": true, "location": true, "native_geofences": false, "actions": ["lock"]},
      "detail": "TimeoutError"
    }
  ]
}
```

No mutation endpoint is added in this slice.

- [ ] **Step 4: Write RED frontend/E2E assertions**

Extend the browser smoke to assert:

- enabled Google/OIDC login buttons are keyboard accessible and initiate the
  server-side flow; password login remains available;
- provider status is visible;
- each device detail shows provider and location quality;
- rejected location explains `unknown` rather than displaying `outside`;
- 20 existing views still render;
- no console, request or page errors.

- [ ] **Step 5: Implement UI and translations, then run GREEN**

Use existing rendering helpers and reicon library. Do not add a new framework. Add ES/EN strings to the bidirectional dictionary.

Run:

```bash
node --check static/app.js
node --check static/i18n.js
/Users/adri/geofence-uem/.venv/bin/python -m pytest tests/test_multiuem_api.py tests/test_deployment_auth_modes.py tests/test_webapp_e2e_dashboard.py -q
```

Expected: all pass and no JS syntax errors.

- [ ] **Step 6: Commit**

```bash
git add saas_server.py saas/auth.py bin/lucidfence static/app.js static/i18n.js docs/openapi.json tests/test_multiuem_api.py tests/test_deployment_auth_modes.py tests/test_webapp_e2e_dashboard.py
git commit -m "feat(ui): support hosted login and local Multi-UEM ownership"
```

---

### Task 7: Whole-product verification, security review and documentation

**Files:**
- Modify: `README.md`
- Create: `docs/MULTI_UEM.md`
- Modify: plan checkboxes and `.superpowers/sdd/progress.md` (ledger is scratch/ignored)

**Interfaces:**
- Documents exact config schema, supported/live limitations, quality defaults, migration from legacy and safety boundaries.

- [ ] **Step 1: Update documentation without overclaims**

Include a capability matrix distinguishing contract-tested, simulated and credential-validated-live providers. State external credentials not exercised as `NOT VALIDATED`, never PASS.

- [ ] **Step 2: Run full static and secret gates**

```bash
git diff --check
node --check static/app.js
node --check static/i18n.js
gitleaks git --redact --no-banner
```

Expected: exit 0, no leaks.

- [ ] **Step 3: Run full honest suite**

```bash
/Users/adri/geofence-uem/.venv/bin/python tests/run_tests.py
```

Expected: `0 failed`. Restore only generated tracked telemetry after the run.

- [ ] **Step 4: Verify product live in browser**

Verify both deployment paths. Start local mode from this worktree on a free loopback port, bootstrap the local owner, and confirm providers/device evidence/geofence views. Then start hosted mode in a separate temporary data root, confirm anonymous access is denied, login succeeds, and the same Multi-UEM views work. Assert browser console and failed requests are empty. Capture screenshot paths for evidence but do not commit them.

- [ ] **Step 5: Dispatch final independent code/security review**

Reviewer receives spec path, plan path and complete branch diff package. It must inspect tenant isolation, password auth, OIDC state/nonce/PKCE, issuer/redirect validation, identity linking, token redaction, hosted login, local loopback ownership, non-loopback fail-closed behavior, hosted/local Multi-UEM parity, identity ambiguity, stale/future/inaccurate locations, action routing, SSRF/redirects, error sanitization, legacy behavior, UI claims and test honesty. Fix every Critical/Important issue and re-review.

- [ ] **Step 6: Clean runtime and verify workspace**

Stop only the server started by this task. Confirm its PID is gone and port is free. Restore generated telemetry, remove screenshots/temp reports, and verify `git status --short` contains only intended docs/checklist changes.

- [ ] **Step 7: Commit final docs**

```bash
git add README.md docs/MULTI_UEM.md docs/superpowers/plans/2026-07-22-multi-uem-geofencing.md
git commit -m "docs: publish verified multi-UEM operations guide"
```

## Plan Self-Review Checklist

- Spec coverage: tasks cover all 16 acceptance criteria.
- Compatibility: legacy path remains explicit in Tasks 3 and 4.
- Type consistency: canonical/provider IDs and evidence types have one definition in Task 1.
- Security: tenant isolation, secret sanitization and URL safety have explicit tests.
- Test honesty: every new behavior has an observed RED command before production.
- No placeholders: commands, files, signatures, response shapes and expected outcomes are specified.
- Scope: concurrency, microservices, OAuth onboarding, billing and autonomous destructive execution remain excluded.
