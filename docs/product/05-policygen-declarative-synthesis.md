# Propuesta de Producto: PolicyGen - Auto-Síntesis Determinista de Políticas Declarativas UEM

## 1. Resumen Ejecutivo
PolicyGen traduce reglas de políticas complejas de LucidFence (`internal/domain/policy`) en artefactos declarativos nativos optimizados para cada ecosistema UEM compatible: Apple DDM JSON declarations, Microsoft Windows DSC PowerShell/MOF scripts, y Android AMAPI JSON policies.

## 2. Definición del Problema
- Aunque los adaptadores UEM soportan capacidades declarativas (como `supports_amapi_policy` o `supports_ddm`), los administradores deben redactar manualmente las configuraciones JSON/DSC complejas.
- Falta una herramienta que tome los veredictos de riesgo de LucidFence y genere de forma determinista la política declarativa exacta lista para sincronizar.

## 3. Especificación Funcional
- **Compilador Multiorigen**: Toma una política de `internal/domain/policy` y compila los bloques `Field/Op/Value` a las sintaxis declarativas correspondientes:
  - Apple DDM: Objetos de configuración `com.apple.configuration.management.status-subscriptions`.
  - Windows DSC: Recursos `Configuration` de PowerShell DSC validados.
  - Android AMAPI: Documentos de política declarativa `Policy` de AMAPI.
- **Validación Sintáctica Local**: Garantiza que el esquema compilado cumple con las especificaciones de Apple, Microsoft y Google antes de enviarlo al conector UEM.

## 4. Arquitectura de Implementación (Go / Local-First)
- **Nuevo Paquete Domain**: `internal/domain/policygen`.
- **Cero Dependencias Externas**: Implementado enteramente en Go con stdlib (`encoding/json`, `text/template`).
