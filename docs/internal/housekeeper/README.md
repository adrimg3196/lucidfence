# Housekeeper — loop diario de limpieza (1 cleanup probado por día)

Loop de housekeeping del repo. Cadencia: diaria, ~01:00 hora de Madrid.
Esta carpeta es el **hogar del contenido** del loop (tarjetas, diferidos,
métricas), no su workspace: los cambios se hacen siempre en un worktree
fresco desde `origin/main`, fuera de esta carpeta y fuera del checkout de
trabajo.

## Ciclo (una ejecución)

1. **Sondeo**: código muerto, ficheros/comentarios rancios, dependencias sin
   uso, duplicación, nombres inconsistentes. Protegido SIEMPRE: trabajo
   activo, cambios sin commitear, ficheros generados, y todo lo incierto.
2. **Un candidato**: elegir UNO y probar que es genuinamente de bajo riesgo
   con evidencia concreta (referencias con `git grep`, historial, diff,
   contenido de LICENSE…) ANTES de tocarlo. Sin prueba → a
   `deferred-candidates.md` (se lista, nunca se borra).
3. **Cambio mínimo coherente** en un worktree fresco desde `origin/main`
   (fuera de esta carpeta). Se conserva solo si build + tests + batería
   runtime siguen verdes.
4. **PR**: una por cleanup. Si hay una PR del Housekeeper aún abierta
   (sin mergear), NO se abre otra ese día: solo se refrescan los estados de
   las existentes y las tarjetas.
5. **Tarjeta** en `cards/`: una por PR, markdown con front matter
   `type: open` | `type: merged` (+ `pr`, `date`, `title`).
6. **Métrica**: cleanups aterrizados (mergeados) por día en `metrics.md`.
7. Dashboard (kanban de tarjetas + gráfico de cleanups/día) regenerado a
   partir de esta carpeta.

## Reglas duras

- Máx. 1 PR nueva por día; PRs del Housekeeper se titulan `housekeeping: …`.
- La evidencia va SIEMPRE en el cuerpo de la PR (qué se probó y cómo).
- Nada de borrar en caliente lo incierto: diferir es un resultado válido.
- Los gates del repo aplican íntegros (CI + batería runtime).
