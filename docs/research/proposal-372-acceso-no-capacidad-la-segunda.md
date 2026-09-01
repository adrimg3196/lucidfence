# Investigación: Acceso, no capacidad: la segunda opinión no tiene UI y el wizard no declara scopes

**Issue:** #372

## Resumen

Dos hallazgos verificados de la pasada de especialistas del 2026-08-31 que NO entraron en el ciclo (disciplina de un cambio por concern), con la evidencia lista para que el siguiente ciclo los tome.

## 1. La "segunda opinión" no tiene pantalla — el diferenciador es invisible

El hallazgo más valioso que produce LucidFence —«tu UEM dice que este equipo cumple y no cumple»— solo existe si el admin sabe hacer `curl`.

**Verificado en vivo** (tenant demo + `run-once`): `GET /api/second-opinion` dev

## Próximos pasos

- [ ] Investigar requerimientos
- [ ] Implementar solución
- [ ] Escribir tests
- [ ] Verificar con verify.py
- [ ] Crear PR

---

*Generado por Hermes Agent el 2026-09-01*
