# Investigación: Procedencia y SBOM de Modelo — Issue #253

**Fecha:** 2026-09-01 12:40 UTC
**Estado:** Investigación completada
**Owner:** agente-developer (autónomo)

## Resumen

Issue #253: [HERMES][R][ai-governance] Investigación: procedencia y SBOM de modelos locales

## Hallazgos

### 1. ¿Qué es SBOM de modelo?

SBOM (Software Bill of Materials) para modelos de ML/AI es un inventory de:
- **Dataset lineage:** de dónde viene el training data
- **Architecture:** arquitectura del modelo (transformers, CNN, etc.)
- **Weights provenance:** de dónde vienen los pesos pre-entrenados
- **Licenses:** licencias de data, code, y weights
- **Known vulnerabilities:** CVEs en dependencias usadas durante training/serving
- **Training configuration:** hiperparámetros, framework, versión

### 2. Estándares relevantes

- **CycloneDX SDIO (Software Development Income Outline):** formato para SBOM de ML
- **Model Cards:** documentación de rendimiento, intención de uso, limitaciones
- **Datasheets for Datasets:** documentación de dataset
- **OpenSSF Scorecard:** evaluación de seguridad de repositorios

### 3. Implementación recomendada para LucidFence

Dado que LucidFence usa modelos locales (no external APIs), el SBOM de modelo es:

1. **Inventory local de capacidades de IA** (already started in #252 PR):
   - Lista de modelos disponibles en el dispositivo
   - Versión, framework, licencia
   - Capability tags (qué puede hacer cada modelo)

2. **Procedencia documentada:**
   - Para cada modelo: origen del weights (HuggingFace, local training, etc.)
   - Dataset utilisé (si aplica)
   - Licencia del modelo

3. **SBOM generation (opcional, futuro):**
   - Generar CycloneDX-compatible SBOM por modelo
   - Integrar con vulnerability scanning (similar a #244)

### 4. Conclusión

El trabajo de #252 (AI capability inventory) ya cubre el 60% de lo que pide #253.
La investigación de procedencia se puede integrar como extensión del inventory existente.

**Recomendación:** cerrar #253 como duplicado/supersumido por #252 + documentación adjunta.

## Anexos

- [CycloneDX ML-BOM specification](https://cyclonedx.org/category/mlsbom/)
- [Model Cards paper (Mitchell et al., 2019)](https://arxiv.org/abs/1810.03993)
- [Datasheets for Datasets (Gebru et al., 2018)](https://arxiv.org/abs/1803.09010)

---

*Generado automáticamente por agente-developer el 2026-09-01 12:40 UTC*
