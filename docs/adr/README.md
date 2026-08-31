# ADR — Architecture Decision Records

Este directorio contiene los registros de decisiones de arquitectura del proyecto.

## Plantilla

Cada ADR sigue el formato MADR (Markdown Architectural Decision Records):

```markdown
# ADR-NNNN: Título de la decisión

## Estado
Propuesto | Aprobado | Deprecado | Supersedado

## Contexto
Qué problemática o requisito motiva esta decisión.

## Decisión
Qué elegimos y por qué.

## Consecuencias
Lo que cambia con esta decisión (positivo y negativo).
```

## ADRs existentes

| Número | Título | Estado |
|--------|--------|--------|
| ADR-0001 | Usar stdlib puro, sin frameworks web | Aprobado |
| ADR-0002 | No usar pytest, usar honest runner propio | Aprobado |
| ADR-0003 | Configurar como código ( políticas YAML) | Aprobado |

## Cómo contribuir

Ver [guía de desarrollo](../contributing/DEVELOPMENT.md) para cómo proponer nuevos ADRs.
