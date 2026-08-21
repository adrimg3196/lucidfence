# El consejo directivo — quién ocupa cada silla

> Para el propietario, que es de negocio. Sin jerga: quién hace qué, y qué
> llega hasta ti. El detalle técnico de cada agente está en `.claude/agents/`;
> el contrato de la flota, en `docs/internal/LOOP.md`.

## Las siete sillas

| Silla | Quién la ocupa | Qué vigila |
|---|---|---|
| **CEO** · estrategia y visión | `specialized-chief-of-staff` | Sintetiza la semana entera y es **el único que te escribe**. Traduce a negocio: si te llega, es porque necesita una decisión tuya. |
| **CTO** · tecnología | `engineering-backend-architect` + `specialized-fleet-architect` | Cómo está construido el producto y cómo evoluciona la propia fábrica de agentes. |
| **CFO** · finanzas | `finance-fpa-analyst` | El gasto por ciclo y el cortacircuitos: ningún loop se dispara en coste. |
| **CMO** · marketing | `marketing-seo-specialist` + `marketing-community-builder` | Que quien busca esto nos encuentre, y el contacto con la comunidad. Sin humo. |
| **COO** · operaciones | `project-shepherd` | Que los agentes no se pisen: quién toca qué, cuándo, y qué pasa si dos quieren lo mismo. |
| **LEGAL** · riesgo y cumplimiento | `legal-compliance-counsel` | RGPD (tratamos ubicación de empleados en la UE), integridad de la licencia y que ninguna promesa pública sea indefendible. |
| **DATA** · análisis | `data-business-analyst` | La pregunta que nadie hacía: *¿esto está sirviendo para algo?* Con deltas y fuente, o diciendo "sin señal suficiente". |

Debajo del consejo hay **quince especialistas más** (desarrollo, seguridad
ofensiva y defensiva, calidad, privacidad, limpieza, soporte, releases…). El
mapa completo está en `ORG.md`; el consejo es la capa que decide, no toda la
plantilla.

## Y tú: la decisión final

La regla de oro no cambia y está escrita en `LOOP.md`:

- **El desarrollo del producto es autónomo.** Los agentes deciden, implementan,
  prueban y publican sin pedirte permiso. Esa es la parte que trabaja sola.
- **El producto en manos de un cliente NUNCA es autónomo.** Sobre dispositivos
  reales decide siempre el administrador: modo observación por defecto, y el
  borrado exige dos llaves. Ningún agente puede debilitar eso — es un invariante
  con pruebas que lo protegen.

## Qué debería llegarte, y qué no

**Sí:** un resumen semanal del CEO, y cualquier cosa que necesite tu firma
(riesgo legal serio, un cambio de rumbo, un gasto nuevo).

**No:** errores de compilación, tests rojos, ramas en conflicto, avisos del
sistema de publicación. Eso es trabajo de la fábrica y se arregla dentro. Si un
fallo técnico te está llegando, es un síntoma de que el consejo no está
haciendo su trabajo — no de que tú tengas que aprender a leerlo.
