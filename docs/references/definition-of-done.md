# Definition of Done — LucidFence

Barra fija de proyecto que todo cambio debe superar antes de contar como done.
Complementa (no reemplaza) los criterios de aceptación de cada tarea.

## Correctness
- [ ] Se cumplen los criterios de aceptación de la tarea.
- [ ] El código corre y se comporta como se espera, **verificado en runtime** (server levantado / vitrina abierta en navegador), no solo importado.
- [ ] El nuevo comportamiento tiene tests que fallan sin el cambio y pasan con él.
- [ ] Los tests existentes siguen pasando; sin regresiones (`python3 tests/run_tests.py`).
- [ ] Casos borde y rutas de error manejados, no solo el happy path.

## Quality
- [ ] El código revela intención por nombres/estructura; sin comentarios que expliquen el *qué*.
- [ ] Sin lógica de negocio duplicada.
- [ ] Sin código muerto, output de debug, ni bloques comentados.
- [ ] Cambio acotado a la tarea; sin refactors no relacionados.

## Integration
- [ ] El cambio funciona con el resto del sistema, no aislado.
- [ ] El runner de tests descubre y corre el nuevo test (sin `SystemExit` que aborte el discovery).
- [ ] Compatibilidad hacia atrás considerada en cualquier API pública.

## Documentation
- [ ] Interfaces públicas, APIs y comportamiento visible documentados.
- [ ] Decisiones de arquitectura dignas de preservar registradas (ADR).
- [ ] La doc describe el estado actual en lenguaje atemporal.

## Ship-readiness
- [ ] Implicaciones de seguridad revisadas para cualquier input no confiable, auth o manejo de datos.
- [ ] Observabilidad en paths críticos (logs estructurados del engine).
- [ ] Ruta de rollback existe para cualquier cambio arriesgado.
- [ ] El humano revisó y aprobó antes de merge/deploy.

## Red Flags
- "Está hecho, solo no lo he corrido": trabajo no verificado no está done.
- "Los tests pasan" como sinónimo de done mientras se saltan doc/regresiones/verificación runtime.
- Barra renegociada según presión de deadline.
- "Done" declarado antes de la revisión humana en cambios que la necesitan.
