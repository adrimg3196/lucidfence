# Arquitectura de LucidFence 2.0

Un módulo Go, un binario. Este documento es normativo: `internal/arch` y
`depguard` (`.golangci.yml`) fallan la CI si el código se desvía de él. La
spec completa está en `docs/superpowers/specs/2026-09-05-lucidfence-2-go-rewrite-design.md`.

## Principios

1. Local-first: el dato del tenant vive en la máquina del tenant. Cero telemetría.
2. Complemento del UEM, nunca un UEM.
3. El runtime lo decide el admin: `observe` por defecto, doble llave para `wipe`.
4. Gratis y open source (Apache-2.0).
5. Todo claim se verifica en vivo contra el binario (batería runtime).
6. Estado en JSON/JSONL en disco, sin base de datos.

## Paquetes

| Paquete | Responsabilidad |
|---------|-----------------|
| `cmd/lucidfence` | `main()` y despacho de subcomandos. Sin lógica de negocio. |
| `cmd/battery` | Ejecuta la batería runtime contra un binario compilado. Solo CI y desarrollo. |
| `internal/version` | Versión y commit del binario, fijados por `-ldflags`. |
| `internal/web` | `embed.FS` del frontend compilado y handler SPA con fallback. |
| `internal/arch` | Tests que hacen cumplir límites físicos, allowlists y este documento. |
| `internal/battery` | Checks en vivo (`RUNTIME: N/N`). Cada claim de producto añade uno. |
| `internal/domain/geo` | Geometría esférica: distancias, punto en polígono, distancia a polilínea. Sin I/O. |
| `internal/domain/action` | Enum de acciones UEM y resultado normalizado de ejecución. |
| `internal/domain/fence` | Geocercas círculo/polígono, pertenencia, validación y acciones por evento. |
| `internal/domain/route` | Rutas con corredor: distancia a la polilínea, asignación por dispositivo. |
| `internal/domain/poi` | Puntos de interés y su exportación GeoJSON. |
| `internal/domain/device` | Dispositivo normalizado, inventario, veredicto de riesgo, trail. |
| `internal/domain/transition` | Evaluación de geocerca por ciclo y detección de transiciones. |
| `internal/store` | Persistencia JSON/JSONL atómica por organización; ficheros 0600, directorios 0700. |
| `internal/uem` | Contrato `Adapter`, capacidades, resultado de conexión y registro de conectores. |
| `internal/uem/simulation` | Flota simulada con seed embebida; mueve dispositivos por waypoints y simula acciones. |
| `internal/config` | `config.json`: defaults seguros, validación con nombre de campo, guardado 0600. |
| `internal/engine` | Ciclo de evaluación bajo TryLock, planificación de acciones, guardarraíles (observe por defecto), datos demo. |
| `internal/auth` | Usuarios locales (argon2id), sesiones con CSRF y caducidad, token local para CLI/MCP, matriz de roles y capacidades. |

Los paquetes de M1 en adelante (`internal/domain/...`, `internal/engine`,
`internal/uem/...`, `internal/store`, `internal/auth`, `internal/api`,
`internal/notify`, `internal/posture`, `internal/reports`, `internal/mcp`,
`internal/config`, `internal/migrate`) se añaden a esta tabla en el commit que
los crea; el test `TestArchitectureDocListsEveryPackage` lo exige.

## Reglas de dependencia

| Paquete | Puede importar del proyecto |
|---------|-----------------------------|
| `internal/domain` | nada (solo stdlib y otros subpaquetes de `domain`) |
| `internal/uem` y conectores | `domain`, `uem` |
| `internal/store` | `domain` |
| `internal/notify`, `internal/posture`, `internal/reports` | `domain`, `store` |
| `internal/engine` | `domain`, `uem`, `store`, `notify`, `posture`, `config` |
| `internal/auth` | `domain`, `store` (+ `golang.org/x/crypto`) |
| `internal/api` | `engine`, `auth`, `store`, `reports`, `domain`, `uem` (nunca un conector concreto), `config`, `version` |
| `internal/mcp` | `api` (cliente HTTP local) |
| `internal/web`, `internal/version`, `internal/config`, `internal/arch`, `internal/battery` | solo stdlib |
| `cmd/*` | todo |

## Límites físicos

- Ficheros Go ≤ 400 líneas; componentes `.tsx` ≤ 300 líneas. Excepción solo con
  `// limits:allow #<issue>` en la primera línea.
- Funciones Go ≤ 60 líneas y ≤ 40 sentencias; complejidad ciclomática ≤ 15.
- Dependencias externas solo las de `internal/arch/allowlist_go.txt` y
  `internal/arch/allowlist_npm.txt`.

## Ficheros protegidos (CODEOWNERS)

`ARCHITECTURE.md`, `.github/`, `go.mod`, `go.sum`, `.golangci.yml`,
`web/package.json`, `web/package-lock.json`, `internal/arch/`,
`internal/battery/`, `internal/engine/guardrails*`, `scripts/`,
`scripts/coverage.sh`, `.gitleaks.toml`. Cualquier cambio exige aprobación
del propietario aunque la CI esté verde.
