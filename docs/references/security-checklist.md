# Security Checklist — LucidFence (Python / UEM)

Referencia de seguridad web. Usar junto con el skill security-and-hardening.
Adaptado de agent-skills/references/security-checklist.md al stack Python/UEM.

## Threat Modeling (empieza aquí)
- [ ] Fronteras de confianza mapeadas (requests HTTP, webhooks SOAR, APIs MDM de terceros, output de MoA).
- [ ] Activos nombrados (credenciales tenant, PII de dispositivos, acciones de remediación, datos de geocerca).
- [ ] STRIDE por frontera (Spoofing, Tampering, Repudiation, Info disclosure, DoS, Elevation).
- [ ] Abuse cases escritos junto a los use cases ("¿cómo abusaría de esto?").

## Pre-Commit
- [ ] Sin secretos en código (`git diff --cached | grep -i "password\|secret\|api_key\|token"`).
- [ ] `.gitignore` cubre: `.env`, `*.pem`, `*.key`, `data/*.tmp`.
- [ ] `.env.example` usa placeholders (no secretos reales).

## Authentication (LucidFence usa sesiones por cookie)
- [ ] Passwords hasheados (bcrypt/scrypt/argon2) — ver `core/auth.py`.
- [ ] Cookie de sesión: `HttpOnly`, `Secure` (en prod), `SameSite=Lax`.
- [ ] Expiración de sesión configurada.
- [ ] Rate limiting en login.
- [ ] NO hay endpoint `/api/auth/demo` expuesto en producción (ver test de seguridad).

## Authorization
- [ ] Cada endpoint protegido chequea autenticación.
- [ ] Cada acceso a recurso chequea ownership/rol (previene IDOR entre tenants).
- [ ] Acciones admin requieren rol admin.
- [ ] Aislamiento multi-tenant: un tenant no lee dispositivos de otro.

## Input Validation
- [ ] Todo input validado en fronteras (rutas API, handlers).
- [ ] Allowlists, no denylists.
- [ ] Longitudes de string acotadas; rangos numéricos validados.
- [ ] Email/URL/date validados con librerías propias.
- [ ] Uploads: tipo restringido, tamaño límite, contenido verificado.
- [ ] Consultas parametrizadas (sin concatenación de strings → no SQLi).
- [ ] URLs validadas antes de redirect (open redirect).
- [ ] Fetches server-side allowlist; IPs privadas/reservadas bloqueadas (SSRF).

## Security Headers (si se sirve HTTP directo)
```
Content-Security-Policy: default-src 'self'
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
```

## CORS (solo si aplica)
- Nunca `Access-Control-Allow-Origin: *` con credentials.
- Restringir a orígenes conocidos del tenant.

## Data Protection
- [ ] Campos sensibles excluidos de respuestas API (hashes, tokens).
- [ ] Datos sensibles no se loguean.
- [ ] HTTPS para toda comunicación externa (MDM, Atomic Mail).
- [ ] Backups de DB encriptados.

## Dependency Security
- [ ] Un solo lockfile (`requirements.txt`) commiteado; CI no lo reescribe.
- [ ] `pip-audit` / `safety` en CI para CVEs conocidos.
- [ ] Nuevas dependencias revisadas (propiedad, mantenimiento, typosquatting).
- [ ] Scripts de lifecycle de dependencias bloqueados antes del primer execution.

## AI / LLM Security (MoA local)
- [ ] Output del modelo tratado como no confiable — nunca en `eval`/SQL/shell/`innerHTML`/rutas de archivo.
- [ ] Prompt injection asumido; permisos en código, no en el system prompt.
- [ ] Secretos y datos cross-tenant fuera de la ventana de contexto.
- [ ] Permisos de tools acotados; acciones destructivas requieren confirmación.
- [ ] Límites de tokens/rate/recursión configurados.

## Error Handling
```python
# Producción: error genérico, sin internals
self.send_json({"error": {"code": "INTERNAL_ERROR", "message": "Algo falló"}}, 500)
# NUNCA en producción: exponer err.message / traceback / query SQL
```

## OWASP Top 10 (referencia rápida)
| # | Vulnerabilidad | Prevención |
|---|---|---|
| 1 | Broken Access Control | Auth en cada endpoint, ownership |
| 2 | Cryptographic Failures | HTTPS, hashing fuerte, sin secretos en código |
| 3 | Injection | Queries parametrizadas, validación |
| 4 | Insecure Design | Threat modeling, spec-driven |
| 5 | Security Misconfiguration | Headers, permisos mínimos, auditar deps |
| 6 | Vulnerable Components | `pip-audit`, deps actualizadas |
| 7 | Auth Failures | Passwords fuertes, rate limit, sesión |
| 8 | Data Integrity Failures | Verificar updates/deps, artifacts firmados |
| 9 | Logging Failures | Loguear eventos de seguridad, no secretos |
| 10 | SSRF | Validar/allowlist URLs, restringir outbound |
