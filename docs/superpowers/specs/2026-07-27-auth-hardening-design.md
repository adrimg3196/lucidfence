# Auth Hardening — Design (superpowers:brainstorming)

Fecha: 2026-07-27 · Estado: aprobado (conducción autónoma)

## Problema
`saas/auth.py` permite fuerza bruta ilimitada en `authenticate()`, filtra
existencia de usuarios por timing (no ejecuta PBKDF2 si el email no existe) y
nunca purga sesiones expiradas de `_sessions.json`.

## Enfoques considerados
1. Lockout persistente por usuario en `_users.json` — sobrevive reinicios pero
   permite DoS de cuentas ajenas escribiendo a disco por cada intento.
2. Throttling en memoria por (email) con ventana deslizante — barato, sin I/O,
   se resetea al reiniciar (aceptable en local-first). **ELEGIDO.**
3. CAPTCHA/2FA — fuera de alcance $0/local-first (YAGNI).

## Diseño
- `AuthStore.authenticate()`:
  - ventana deslizante en memoria: máx 5 fallos por email en 300 s → devuelve
    `None` (bloqueado) hasta que la ventana drene. Config vía
    `LUCIDFENCE_LOGIN_MAX_FAILS` / `LUCIDFENCE_LOGIN_WINDOW_S`.
  - login correcto limpia los fallos del email.
  - email inexistente: se ejecuta un `verify_password` contra un hash dummy
    precomputado (mismo coste PBKDF2) → sin oráculo de timing.
- `AuthStore.purge_expired_sessions()`: elimina todas las sesiones caducadas y
  persiste; se invoca de forma oportunista en `create_session`.

## Criterios de éxito
- Tests nuevos RED→GREEN; suite completa sigue 100% verde (254 + nuevos).
- Sin dependencias nuevas, stdlib-first, sin secretos.

## Limitaciones aceptadas (post-review independiente PASS)
- Lockout en memoria: se resetea al reiniciar el proceso (aceptable local-first).
- Lockout por email = posible DoS dirigido de cuenta (tradeoff clásico); mitigable
  a futuro con clave email+IP si el threat model cambia a internet-facing.
- Salt dummy fijo "00"*16: solo para paridad de timing, nunca almacena passwords.
