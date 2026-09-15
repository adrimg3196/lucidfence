# Hermes Guidance & Architectural Learnings for LucidFence 2.0 (NOVA Discovery)

## Contexto de Producto
LucidFence 2.0 es un motor de riesgo explicable y geocercado local-first escrito en Go como un binario único estático con dashboard embebido.
**REGLA DE ORO:** No existen cuotas, planes ni tiers de pago. Todo es gratis y open source (Apache-2.0). Cero telemetría.

## Guía Técnica para Hermes al implementar la Hoja de Ruta (Horizonte EXPLORE)

### 1. Convenciones de Arquitectura en Go
- **Cero dependencias externas no autorizadas**: Consultar `internal/arch/allowlist_go.txt` y `ARCHITECTURE.md` antes de añadir paquetes externos.
- **Límites Físicos por Archivo**:
  - Archivos `.go` $\le$ 400 líneas.
  - Funciones Go $\le$ 60 líneas y $\le$ 40 sentencias.
  - Complejidad ciclomática $\le$ 15.
- **Aislamiento de `internal/domain`**:
  - Los paquetes dentro de `internal/domain` no pueden realizar I/O, I/O de disco ni llamadas de red.
  - `domain` solo consume stdlib u otros subpaquetes dentro de `domain`.

### 2. Principios Local-First para las Nuevas Iniciativas
- **LucidMesh (`internal/domain/mesh`)**: Mantener el estado de consenso en memoria volátil en cada evaluación bajo `TryLock` del motor (`internal/engine`).
- **ChronosFence (`internal/domain/chronos`)**: Reutilizar el cálculo esférico existente en `internal/domain/geo` sin alterar las constantes de `internal/domain/integrity`.
- **ZK-Geofence (`internal/domain/zkattest`)**: Usar construcciones deterministas de Go stdlib (`crypto/sha256`, `crypto/ed25519`) para la atestación de pruebas sin sobrecargar la memoria.
- **GhostFence (`internal/domain/ghostfence`)**: Respetar siempre las llaves de guardarraíl de `internal/engine/guardrails` y el modo `observe` por defecto.
- **PolicyGen (`internal/domain/policygen`)**: Compilar únicamente usando plantillas deterministas localmente (`text/template`, `encoding/json`).

### 3. Verificación de Código y Cierre
- Ejecutar siempre `go test ./...` para verificar que la suite completa de Go pasa sin errores.
- Verificar que el mapa de arquitectura en `ARCHITECTURE.md` se actualice si se crea un paquete nuevo en `internal/`.
